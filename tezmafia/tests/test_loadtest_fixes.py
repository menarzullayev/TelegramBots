"""Fixes for what the 1M-user / 1M-game load test found (see docs/LOADTEST.md)."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from tests.test_bot_e2e import FakeBot, _ready_game, _settings
from tezmafia import bot as botmod
from tezmafia.bot import App
from tezmafia.db import Store
from tezmafia.engine import Phase, Winner, player_won, start, win_check
from tezmafia.i18n import t


@pytest.fixture
async def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    store = Store(f"sqlite+aiosqlite:///{tmp_path}/data/t.db")
    await store.init()
    application = App(_settings(), store, FakeBot())  # type: ignore[arg-type]
    botmod.app = application
    application.dm = AsyncMock(return_value=True)  # type: ignore[method-assign]
    yield application
    for task in application.timers.values():
        task.cancel()
    await store.engine.dispose()


def _finished(chat_id: int = -100, winner: str | None = "town", n: int = 5):
    g = _ready_game(n)
    g.chat_id = chat_id
    start(g)
    g.winner, g.phase = winner, Phase.FINISHED
    return g


# --- logic -----------------------------------------------------------------------------------


def test_nobody_alive_is_a_draw_and_nobody_wins() -> None:
    g = _ready_game(5)
    start(g)
    for p in g.players:
        p.alive = False
    assert win_check(g) == Winner.DRAW and g.phase == Phase.FINISHED
    assert not any(player_won(g, p) for p in g.players)


def test_lone_arsonist_wins() -> None:
    g = _ready_game(5)
    start(g)
    for p in g.players:
        p.alive = p.seat == 1
    g.players[0].role, g.players[0].faction = "arsonist", "neutral"
    assert win_check(g) == Winner.ARSONIST
    assert [p for p in g.players if player_won(g, p)] == [g.players[0]]


def test_two_survivors_without_a_killer_keep_playing() -> None:
    g = _ready_game(5)
    start(g)
    for p in g.players:
        p.alive = p.seat in (1, 2)
    g.players[0].role, g.players[0].faction = "mage", "neutral"
    g.players[1].role, g.players[1].faction = "citizen", "town"
    assert win_check(g) is None  # not a draw: the vote can still decide it


@pytest.mark.asyncio
async def test_draw_card_says_draw(app: App) -> None:
    g = _finished(winner="draw")
    for p in g.players:
        p.alive = False
    await app.record_stats(g)
    captions = [c[2]["caption"] for c in app.bot.calls if c[0] == "send_photo"]
    assert captions and all(c.startswith(t("uz", "card.draw")) for c in captions)
    assert (await app.store.get_account(g.players[0].user_id))["wins"] == 0


# --- database --------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hot_queries_use_indexes(app: App) -> None:
    async with app.store.engine.connect() as conn:
        async def plan(sql: str) -> str:
            return " ".join(r[3] for r in await conn.execute(text("EXPLAIN QUERY PLAN " + sql)))

        assert "ix_games_active" in await plan("SELECT * FROM games WHERE chat_id = 1 AND status != 'finished' ORDER BY version DESC")
        assert "ix_games_active" in await plan("SELECT * FROM games WHERE status != 'finished'")
        assert "ix_stats_top" in await plan("SELECT * FROM stats ORDER BY wins DESC, games DESC LIMIT 10")
        assert "ix_stats_daily" in await plan("SELECT user_id FROM stats WHERE daily_last = 'x' AND daily_streak >= 2")
        assert "TEMP B-TREE" not in await plan(
            "SELECT * FROM season_stats WHERE season = 's' AND chat_id = 0 ORDER BY wins DESC, games DESC LIMIT 10")


@pytest.mark.asyncio
async def test_record_game_matches_the_separate_calls(app: App) -> None:
    rows = [(7, "A", True, True, False), (8, "B", False, False, True)]
    totals = await app.store.record_game("g1", -5, rows, "2026-10", "2026-W42", (15, 3))
    assert totals == {7: {"games": 1, "wins": 1, "xp": totals[7]["xp"]}, 8: {"games": 1, "wins": 0, "xp": totals[8]["xp"]}}
    for uid, name, won, alive, afk in rows:
        await app.store.bump_stat(uid + 100, name, won, alive)
        await app.store.bump_season("2026-10", -5, uid + 100, name, won)
        await app.store.bump_week("2026-W42", uid + 100, name, won, 1 + 3 * won)
        await app.store.adjust_fair_play(uid + 100, afk, 15, 3)
    for uid in (7, 8):
        a, b = await app.store.get_account(uid), await app.store.get_account(uid + 100)
        assert (a["games"], a["wins"], a["coins"], a["gems"], a["xp"]) == (b["games"], b["wins"], b["coins"], b["gems"], b["xp"])
        assert await app.store.fair_play(uid) == await app.store.fair_play(uid + 100)
    assert [r[1:] for r in await app.store.season_top("2026-10", chat_id=-5)][:2] == [(1, 1), (1, 1)]
    assert {u for u, _, _ in await app.store.week_top("2026-W42", limit=10)} == {7, 8, 107, 108}
    assert [g.id for g in await app.store.user_games(7)] == []  # linked, but not a stored game


@pytest.mark.asyncio
async def test_retry_only_retries_locks(app: App) -> None:
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise OperationalError("UPDATE", {}, Exception("database is locked"))
        return "ok"

    assert await app.store.retry(flaky) == "ok" and calls["n"] == 3

    async def broken():
        raise OperationalError("UPDATE", {}, Exception("no such table: x"))

    with pytest.raises(OperationalError):
        await app.store.retry(broken)

    async def always_locked():
        raise OperationalError("UPDATE", {}, Exception("database is locked"))

    with pytest.raises(OperationalError):
        await app.store.retry(always_locked, attempts=2)


@pytest.mark.asyncio
async def test_cache_is_off_by_default_and_expires(app: App) -> None:
    n = {"v": 0}

    async def value():
        n["v"] += 1
        return n["v"]

    assert await app.store.cached("k", value) == 1
    assert await app.store.cached("k", value) == 2  # ttl 0: always fresh (tests, scripts)
    app.store.cache_ttl = 0.1
    assert await app.store.cached("k", value) == 3
    assert await app.store.cached("k", value) == 3  # served from cache
    await asyncio.sleep(0.15)
    assert await app.store.cached("k", value) == 4


@pytest.mark.asyncio
async def test_delete_user_scrubs_only_own_games_including_cancelled(app: App) -> None:
    mine = _finished()
    cancelled = _finished(winner=None)  # cancelled games are finished without stats; save() still links them
    other = _finished()
    for p in other.players:
        p.user_id += 1000
    for g in (mine, cancelled, other):
        await app.store.save(g)
    await app.store.link_game(mine.id, [p.user_id for p in mine.players])
    result = await app.store.delete_user(100)
    assert result["games"] == 2
    for g in (mine, cancelled):
        stored = await app.store.load(g.id)
        assert stored.by_user(100).first_name == "—" and stored.by_user(101).first_name == "P1"
    assert (await app.store.load(other.id)).by_user(1100).first_name == "P0"
    assert await app.store.user_games(100) == []


@pytest.mark.asyncio
async def test_report_counts_in_sql(app: App) -> None:
    a, b, c = _finished(-1), _finished(-1, winner=None), _finished(-2)
    for p in c.players:
        p.user_id += 50
    for g in (a, b, c):
        await app.store.save(g)
    r = await app.store.report_since(time.time() - 60)
    assert (r["games"], r["cancelled"], r["chats"], r["players"]) == (2, 1, 2, 10)


@pytest.mark.asyncio
async def test_prune_runs_in_batches_and_drops_links(app: App) -> None:
    old = time.time() - 100 * 86400
    async with app.store.engine.begin() as conn:
        await conn.execute(text(
            "INSERT INTO games (id, chat_id, status, payload, version, created_at, updated_at) VALUES (:i, -1, 'finished', '{}', 1, :t, :t)"
        ), [{"i": f"old{i}", "t": old} for i in range(4500)])
        await conn.execute(text("INSERT INTO game_players (game_id, user_id, at) VALUES (:i, 7, 0)"),
                           [{"i": f"old{i}"} for i in range(4500)])
    fresh = _finished()
    await app.store.save(fresh)
    assert await app.store.prune_finished(90) == 4500
    async with app.store.engine.connect() as conn:
        left = (await conn.execute(text("SELECT COUNT(*) FROM game_players WHERE user_id = 7"))).scalar()
    assert left == 0 and await app.store.load(fresh.id) is not None


# --- Telegram call budget --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lobby_edits_are_merged(app: App) -> None:
    app.settings.edit_debounce = 0.05
    g = _ready_game(5)
    g.lobby_message_id = 9
    await app.persist(g)
    for _ in range(6):
        await app.refresh_lobby(g)
    assert not [c for c in app.bot.calls if c[0] == "edit"]
    await asyncio.sleep(0.2)
    assert len([c for c in app.bot.calls if c[0] == "edit"]) == 1


@pytest.mark.asyncio
async def test_long_news_falls_back_to_its_own_dm(app: App) -> None:
    g = _finished()
    p = g.players[0]
    sent = await app.send_card(g, p, True, {"games": 1, "wins": 1, "xp": 40}, extra="x" * 2000)
    caption = [c for c in app.bot.calls if c[0] == "send_photo"][-1][2]["caption"]
    assert sent is False and len(caption) < 1024  # caller then sends the news as a DM
    assert await app.send_card(g, p, True, {"games": 1, "wins": 1, "xp": 40}, extra="news") is True


@pytest.mark.asyncio
async def test_init_links_legacy_games(app: App) -> None:
    g = _finished()
    await app.store.save(g)
    async with app.store.engine.begin() as conn:
        await conn.execute(text("UPDATE games SET updated_at = NULL"))
        await conn.execute(text("DELETE FROM game_players"))
    await app.store.init()  # startup migration
    assert {x.id for x in await app.store.user_games(102)} == {g.id}
    assert (await app.store.delete_user(102))["games"] == 1


@pytest.mark.asyncio
async def test_active_users_stays_on_the_date_range(app: App) -> None:
    for day, uid, ch in (("2026-10-01", 1, "dm"), ("2026-10-02", 1, "group"), ("2026-10-02", 2, "group"), ("2026-09-01", 3, "dm")):
        await app.store.touch_activity(day, uid, ch)
    assert await app.store.active_users("2026-10-01") == 2
    assert await app.store.active_users("2026-10-01", "dm") == 1
    async with app.store.engine.connect() as conn:
        plan = " ".join(r[3] for r in await conn.execute(text(
            "EXPLAIN QUERY PLAN SELECT COUNT(DISTINCT user_id) FROM activity INDEXED BY sqlite_autoindex_activity_1"
            " WHERE day >= '2026-10-01'")))
    assert "ix_activity_user" not in plan and "day>" in plan
    await app.store.optimize()  # must not fail on a fresh database


@pytest.mark.asyncio
async def test_deferred_lobby_edit_never_writes_back_a_stale_game(app: App) -> None:
    from unittest.mock import MagicMock

    from aiogram.exceptions import TelegramBadRequest

    app.settings.edit_debounce = 0.05
    g = _ready_game(5)
    g.lobby_message_id = 9
    await app.persist(g)

    async def start_under_lock() -> None:  # another handler starts the game meanwhile, as handlers do: under the lock
        async with app.game_lock(g.id):
            fresh = await app.store.load(g.id)
            start(fresh)
            await app.persist(fresh)

    racers: list[asyncio.Task] = []

    async def gone(*a, **k):  # the lobby message was deleted: refresh_lobby posts a new one and persists
        if not racers:
            racers.append(asyncio.create_task(start_under_lock()))
            await asyncio.sleep(0.05)
        raise TelegramBadRequest(method=MagicMock(), message="message to edit not found")

    app.bot.edit_message_text = gone  # type: ignore[method-assign]
    await app.refresh_lobby(g)
    await asyncio.sleep(0.3)
    await asyncio.gather(*racers)
    assert (await app.store.load(g.id)).phase != Phase.LOBBY  # the start is not overwritten by the deferred edit


@pytest.mark.asyncio
async def test_unchanged_lobby_is_not_reposted(app: App) -> None:
    from unittest.mock import MagicMock

    from aiogram.exceptions import TelegramBadRequest

    app.settings.edit_debounce = 0
    g = _ready_game(5)
    g.lobby_message_id = 9

    async def same(*a, **k):
        raise TelegramBadRequest(method=MagicMock(), message="Bad Request: message is not modified")

    app.bot.edit_message_text = same  # type: ignore[method-assign]
    await app.refresh_lobby(g)
    assert not [c for c in app.bot.calls if c[0] in ("send_message", "pin")] and g.lobby_message_id == 9


# --- stalemate rule ----------------------------------------------------------------------------


def _quiet_game(alive: int):
    from tezmafia.engine import begin_night

    g = _ready_game(8)
    start(g)
    for p in g.players:
        p.alive = p.seat <= alive
    g.chronicle = [{"n": 0, "seat": p.seat, "cause": "night"} for p in g.players if not p.alive]
    begin_night(g, 0, 1)  # night 1 has happened
    return g


def test_three_quiet_rounds_with_few_alive_is_a_draw() -> None:
    from tezmafia.engine import end_if_stalemate

    g = _quiet_game(2)
    g.deaths_seen = len(g.chronicle)
    assert [end_if_stalemate(g) for _ in range(3)] == [False, False, True]
    assert g.winner == Winner.DRAW and g.phase == Phase.FINISHED and g.alive_players()


def test_big_table_is_never_stopped_by_the_stalemate_rule() -> None:
    from tezmafia.engine import end_if_stalemate

    g = _quiet_game(6)
    g.deaths_seen = len(g.chronicle)
    assert not any(end_if_stalemate(g) for _ in range(10)) and g.phase != Phase.FINISHED


def test_a_death_resets_the_quiet_count() -> None:
    from tezmafia.engine import end_if_stalemate

    g = _quiet_game(3)
    g.deaths_seen = len(g.chronicle)
    end_if_stalemate(g)
    end_if_stalemate(g)
    g.chronicle.append({"n": 3, "seat": 1, "cause": "vote"})
    g.players[0].alive = False
    assert not end_if_stalemate(g) and g.quiet_rounds == 0


def test_old_payloads_do_not_count_past_deaths_as_new() -> None:
    from tezmafia.engine import from_dict, to_dict

    g = _quiet_game(3)
    raw = to_dict(g)
    del raw["quiet_rounds"], raw["deaths_seen"]
    back = from_dict(raw)
    assert back.quiet_rounds == 0 and back.deaths_seen == len(g.chronicle)


@pytest.mark.asyncio
async def test_stalemate_finishes_through_enter_night_with_its_own_text(app: App) -> None:
    from tezmafia import texts

    g = _quiet_game(2)
    g.deaths_seen, g.quiet_rounds = len(g.chronicle), 2
    await app.persist(g)
    app.finish = AsyncMock()  # type: ignore[method-assign]
    await app.enter_night(g)
    app.finish.assert_awaited_once()
    assert g.winner == "draw" and texts.outcome_key(g) == "stalemate"
    assert t("uz", "go.stalemate") in texts.game_over(g, "uz")
    for p in g.players:
        p.alive = False
    assert texts.outcome_key(g) == "draw" and t("uz", "go.draw") in texts.game_over(g, "uz")
