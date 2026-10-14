"""G4: game chronicle, fair-play rating, admin moderation, group statistics."""

from __future__ import annotations

import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.enums import ChatType
from aiogram.types import Chat, User

from tests.test_bot_e2e import FakeBot, FakeMsg, _ready_game, _settings
from tezmafia import bot as botmod
from tezmafia import engine, texts
from tezmafia.bot import App
from tezmafia.db import Store
from tezmafia.engine import Phase, from_dict, kick, player_won, start, to_dict
from tezmafia.i18n import t
from tezmafia.social import FAIR_AFK_PENALTY, FAIR_GAME_BONUS

ADMIN = 1  # _settings().owner_id counts as admin everywhere


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


def _group_msg(app: App, uid: int, text: str, sent: list[str], reply_to: int | None = None) -> FakeMsg:
    msg = FakeMsg(User(id=uid, is_bot=False, first_name=f"U{uid}"), Chat(id=-100, type=ChatType.SUPERGROUP), text, app.bot)
    msg.answer = AsyncMock(side_effect=lambda text, **k: sent.append(text))  # type: ignore[method-assign]
    msg.reply_to_message = (  # type: ignore[attr-defined]
        SimpleNamespace(from_user=User(id=reply_to, is_bot=False, first_name=f"P{reply_to}")) if reply_to else None
    )
    return msg


def _cmd(args: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(args=args)


# --- engine ----------------------------------------------------------------------------------


def test_player_won_matches_every_winner() -> None:
    g = _ready_game(8)
    start(g)
    for w in ("mafia", "town"):
        g.winner = w
        assert {p.user_id for p in g.players if player_won(g, p)} == {p.user_id for p in g.players if p.faction == w}
    g.winner = "maniac"
    g.players[0].role = "maniac"
    assert [p for p in g.players if player_won(g, p)] == [g.players[0]]
    g.winner = None
    assert not any(player_won(g, p) for p in g.players)


def test_chronicle_records_deaths_and_survives_serialization() -> None:
    g = _ready_game(6)
    start(g)
    g.phase, g.night_no = Phase.DAY, 1
    town = next(p for p in g.players if p.faction == "town" and p.role != "lucky")
    assert engine._try_kill(g, town, "vote")
    assert g.chronicle == [{"n": 1, "seat": town.seat, "cause": "vote"}]
    back = from_dict(json.loads(json.dumps(to_dict(g))))
    assert back.chronicle == g.chronicle
    old = to_dict(g)
    del old["chronicle"]
    assert from_dict(old).chronicle == []  # games saved before G4 still load


def test_kick_in_lobby_and_mid_game() -> None:
    g = _ready_game(5)
    done, winner = kick(g, 101)
    assert done and winner is None and not g.by_user(101)
    assert kick(g, 999) == (False, None)
    g = _ready_game(5)
    start(g)
    g.phase = Phase.VOTING
    victim = next(p for p in g.players if p.faction == "town")
    voter = next(p for p in g.players if p.user_id != victim.user_id)
    voter.vote = victim.seat
    done, _ = kick(g, victim.user_id)
    assert done and not victim.alive and voter.vote is None
    assert g.chronicle[-1]["cause"] == "kick"
    assert kick(g, victim.user_id) == (False, None)  # already out


def test_kicking_the_last_mafia_decides_the_game() -> None:
    g = _ready_game(5)
    start(g)
    g.phase = Phase.DAY
    for p in g.players:
        if p.faction == "mafia":
            done, winner = kick(g, p.user_id)
    assert done and winner == "town" and g.phase == Phase.FINISHED


def test_chronicle_lines_name_role_and_cause() -> None:
    g = _ready_game(5)
    start(g)
    g.chronicle = [{"n": 1, "seat": 1, "cause": "night"}, {"n": 1, "seat": 2, "cause": "vote"}, {"n": 1, "seat": 99, "cause": "x"}]
    lines = texts.chronicle_lines(g, "uz")
    assert len(lines) == 2  # unknown seat skipped
    assert lines[0].startswith("🌙 " + t("uz", "chr.night", n=1)) and t("uz", "chr.cause.night") in lines[0]
    assert lines[1].startswith("☀️ " + t("uz", "chr.day", n=1)) and "P1" in lines[1]


# --- fair play -------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fair_play_is_clamped(app: App) -> None:
    assert await app.store.fair_play(7) == 100
    assert await app.store.adjust_fair_play(7, False, FAIR_AFK_PENALTY, FAIR_GAME_BONUS) == 100  # capped
    for _ in range(10):
        score = await app.store.adjust_fair_play(7, True, FAIR_AFK_PENALTY, FAIR_GAME_BONUS)
    assert score == 0  # floored
    assert await app.store.adjust_fair_play(7, False, FAIR_AFK_PENALTY, FAIR_GAME_BONUS) == FAIR_GAME_BONUS


@pytest.mark.asyncio
async def test_game_end_links_players_and_scores_fair_play(app: App) -> None:
    g = _ready_game(5)
    start(g)
    g.winner = "town"
    afk = g.players[0]
    g.chronicle = [{"n": 2, "seat": afk.seat, "cause": "afk"}]
    g.phase = Phase.FINISHED
    await app.persist(g)
    await app.record_stats(g)
    assert await app.store.fair_play(afk.user_id) == 100 - FAIR_AFK_PENALTY
    assert await app.store.fair_play(g.players[1].user_id) == 100
    mine = await app.store.user_games(afk.user_id)
    assert [x.id for x in mine] == [g.id] and mine[0].chronicle == g.chronicle
    assert await app.store.user_games(4242) == []


# --- moderation ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_moderation_is_admin_only(app: App) -> None:
    sent: list[str] = []
    for handler in (botmod.cmd_kick, botmod.cmd_ban, botmod.cmd_unban):
        await handler(_group_msg(app, 55, "/x", sent, reply_to=101), _cmd())  # type: ignore[arg-type]
        assert sent[-1] == t("uz", "mod.admin_only")
    assert not await app.store.is_banned(-100, 101)


@pytest.mark.asyncio
async def test_kick_needs_a_target_and_a_seated_player(app: App) -> None:
    sent: list[str] = []
    await botmod.cmd_kick(_group_msg(app, ADMIN, "/kick", sent), _cmd())  # type: ignore[arg-type]
    assert sent[-1] == t("uz", "mod.usage")
    await botmod.cmd_kick(_group_msg(app, ADMIN, "/kick", sent, reply_to=777), _cmd())  # type: ignore[arg-type]
    assert sent[-1] == t("uz", "mod.not_found")  # no game at all


@pytest.mark.asyncio
async def test_kick_by_seat_from_lobby(app: App) -> None:
    g = _ready_game(5)
    await app.persist(g)
    sent: list[str] = []
    await botmod.cmd_kick(_group_msg(app, ADMIN, "/kick 3", sent), _cmd("3"))  # type: ignore[arg-type]
    assert sent[-1] == t("uz", "mod.kicked", name="P2")
    lobby = await app.store.active_in_chat(-100)
    assert lobby and len(lobby.players) == 4 and not lobby.by_user(102)


@pytest.mark.asyncio
async def test_ban_blocks_joining_until_unban(app: App) -> None:
    g = _ready_game(5)
    await app.persist(g)
    sent: list[str] = []
    await botmod.cmd_ban(_group_msg(app, ADMIN, "/ban", sent, reply_to=101), _cmd())  # type: ignore[arg-type]
    assert sent[-1] == t("uz", "mod.banned", name="P101")
    assert await app.store.is_banned(-100, 101)
    lobby = await app.store.active_in_chat(-100)
    assert lobby and not lobby.by_user(101)  # removed from the open lobby too

    await botmod.cmd_join(_group_msg(app, 101, "/join", sent))  # type: ignore[arg-type]
    assert sent[-1] == t("uz", "mod.you_banned")
    assert not (await app.store.active_in_chat(-100)).by_user(101)

    await botmod.cmd_unban(_group_msg(app, ADMIN, "/unban 101", sent), _cmd("101"))  # type: ignore[arg-type]
    assert sent[-1] == t("uz", "mod.usage")  # 3 digits is neither a seat (1-99 at a table) nor a Telegram id
    await botmod.cmd_unban(_group_msg(app, ADMIN, "/unban", sent, reply_to=101), _cmd())  # type: ignore[arg-type]
    assert sent[-1] == t("uz", "mod.unbanned", name="P101")
    assert not await app.store.is_banned(-100, 101)
    await botmod.cmd_join(_group_msg(app, 101, "/join", sent))  # type: ignore[arg-type]
    assert (await app.store.active_in_chat(-100)).by_user(101)


@pytest.mark.asyncio
async def test_banned_user_cannot_open_a_lobby(app: App) -> None:
    await app.store.ban(-100, 55, ADMIN)
    sent: list[str] = []
    await botmod.cmd_mafia(_group_msg(app, 55, "/game", sent))  # type: ignore[arg-type]
    assert sent[-1] == t("uz", "mod.you_banned")
    assert await app.store.active_in_chat(-100) is None


@pytest.mark.asyncio
async def test_ban_mid_game_can_end_it(app: App) -> None:
    g = _ready_game(5)
    start(g)
    g.phase = Phase.DAY
    await app.persist(g)
    app.finish = AsyncMock()  # type: ignore[method-assign]
    sent: list[str] = []
    for p in [p for p in g.players if p.faction == "mafia"]:
        await botmod.cmd_ban(_group_msg(app, ADMIN, "/ban", sent, reply_to=p.user_id), _cmd())  # type: ignore[arg-type]
    app.finish.assert_awaited_once()
    assert app.finish.await_args.args[0].winner == "town"


@pytest.mark.asyncio
async def test_bans_survive_delete_my_data(app: App) -> None:
    await app.store.credit_wallet(101, "A", coins=1)
    await app.store.ban(-100, 101, ADMIN)
    await app.store.adjust_fair_play(101, True, FAIR_AFK_PENALTY, FAIR_GAME_BONUS)
    await app.store.delete_user(101)
    assert await app.store.is_banned(-100, 101)
    assert await app.store.fair_play(101) == 100  # rating itself is erased


# --- group stats -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_group_stats_counts_results_and_players(app: App) -> None:
    sent: list[str] = []
    await botmod.cmd_groupstats(_group_msg(app, 5, "/groupstats", sent))  # type: ignore[arg-type]
    assert t("uz", "gs.games", n=0) in sent[-1]
    for winner in ("town", "town", "mafia"):
        g = _ready_game(5)
        start(g)
        g.winner, g.phase = winner, Phase.FINISHED
        await app.persist(g)
        await app.record_stats(g)
    stats = await app.store.group_stats(-100, time.strftime("%Y-%m"))
    assert stats["games"] == 3 and stats["results"][0] == ("town", 2) and stats["players"] == 5
    await botmod.cmd_groupstats(_group_msg(app, 5, "/groupstats", sent))  # type: ignore[arg-type]
    assert t("uz", "gs.games", n=3) in sent[-1] and "P0" in sent[-1]


# --- Mini App --------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mini_app_lists_my_games_with_chronicle(app: App) -> None:
    from tezmafia.webapp.server import build_state

    user = {"id": 100, "first_name": "P0"}
    state = await build_state(app, user)
    assert state["games"] == [] and state["strings"]["chr.empty"]
    g = _ready_game(5)
    start(g)
    g.winner, g.phase = "mafia", Phase.FINISHED
    g.chronicle = [{"n": 1, "seat": 2, "cause": "night"}]
    await app.persist(g)
    await app.record_stats(g)
    state = await build_state(app, user)
    entry = state["games"][0]
    assert entry["id"] == g.id and entry["players"] == 5 and len(entry["events"]) == 1
    assert entry["won"] == (g.by_user(100).faction == "mafia")
    assert "<" not in entry["result"] + entry["you"] + entry["events"][0]  # plain text only
    assert "Fair" in state["profile"]["lines"]["fair"]


def test_every_locale_has_the_g4_keys() -> None:
    from pathlib import Path

    keys = ("app.tab_games", "chr.cause.kick", "mod.you_banned", "gs.title", "cmd.groupstats", "profile.fair")
    for path in (Path(botmod.__file__).parent / "locales").glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert all(k in data for k in keys), path.name


@pytest.mark.asyncio
async def test_ban_by_id_shows_the_known_name(app: App) -> None:
    await app.store.credit_wallet(5555555, "Ali", coins=1)
    sent: list[str] = []
    await botmod.cmd_ban(_group_msg(app, ADMIN, "/ban 5555555", sent), _cmd("5555555"))  # type: ignore[arg-type]
    assert sent[-1] == t("uz", "mod.banned", name="Ali")
    await botmod.cmd_unban(_group_msg(app, ADMIN, "/unban 7777777", sent), _cmd("7777777"))  # type: ignore[arg-type]
    assert sent[-1] == t("uz", "mod.unbanned", name="7777777")  # unknown id: the id itself
