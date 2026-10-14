"""H2: bot players fill seats; rewards follow how many people played (DECISION-17)."""

from __future__ import annotations

import random
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.enums import ChatType
from aiogram.types import Chat, User

from tests.test_bot_e2e import FakeBot, FakeMsg, _settings
from tezmafia import bot as botmod
from tezmafia.bot import App
from tezmafia.db import Store
from tezmafia.engine import (
    Phase,
    add_bot,
    begin_lynch,
    begin_night,
    begin_voting,
    bot_lynch_votes,
    bot_night_moves,
    bot_votes,
    humans,
    is_bot,
    join,
    mark_dm_ok,
    new_game,
    start,
)
from tezmafia.i18n import t
from tezmafia.social import reward_tier, week_key


@pytest.fixture
async def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    store = Store(f"sqlite+aiosqlite:///{tmp_path}/data/t.db")
    await store.init()
    application = App(_settings(), store, FakeBot())  # type: ignore[arg-type]
    botmod.app = application
    yield application
    for task in application.timers.values():
        task.cancel()
    await store.engine.dispose()


def _table(people: int, bots: int, base: int = 100, chat_id: int = -100):
    g = new_game(chat_id, base)
    for i in range(people):
        join(g, base + i, f"P{base + i}", None)
        mark_dm_ok(g, base + i)
    for _ in range(bots):
        assert add_bot(g)[0]
    return g


def test_reward_tiers() -> None:
    assert reward_tier(5, 5) == reward_tier(5, 8) == reward_tier(3, 3) == "full"  # no bots, or 5+ people
    assert reward_tier(4, 6) == reward_tier(3, 5) == "half"
    assert reward_tier(2, 5) == reward_tier(1, 5) == "xp"


def test_bots_are_seated_ready_and_counted_apart() -> None:
    g = _table(1, 4)
    assert len(g.players) == 5 and all(p.dm_ok for p in g.players)
    assert [p.user_id for p in g.players if is_bot(p.user_id)] == [-1, -2, -3, -4]
    assert [p.user_id for p in humans(g)] == [100]
    start(g)  # a lone person can practise against bots
    assert add_bot(g) == (False, "not_lobby")
    full = _table(0, 0)
    full.max_players = 2
    add_bot(full)
    add_bot(full)
    assert add_bot(full) == (False, "full")


def test_bots_act_vote_and_never_hit_their_own_side() -> None:
    for seed in range(200):
        rng = random.Random(seed)
        g = _table(1, 7)
        start(g, rng)
        begin_night(g, 0, 1)
        bot_night_moves(g, rng)
        for p in g.players:
            if is_bot(p.user_id) and p.role in ("mafia", "don") and p.night_action:
                assert g.by_seat(p.night_action).faction != "mafia"
        g.phase = Phase.DAY
        begin_voting(g, 0, 1)
        bot_votes(g, rng)
        assert all(p.vote for p in g.alive_players() if is_bot(p.user_id))
        target = g.players[0].seat
        begin_lynch(g, target, 0, 1)
        bot_lynch_votes(g, rng)
        assert all(p.lynch_yes is not None for p in g.alive_players() if is_bot(p.user_id) and p.seat != target)


@pytest.mark.asyncio
async def test_no_messages_go_to_bots(app: App) -> None:
    assert await app.dm(-3, "hi") is True
    assert await app.dm_photo(-3, None, "hi") is True
    assert not [c for c in app.bot.calls if c[1] and c[1][0] == -3]


@pytest.mark.asyncio
async def test_rewards_follow_people_count(app: App) -> None:
    app.dm = AsyncMock(return_value=True)  # type: ignore[method-assign]
    for people, bots, base in ((5, 2, 5000), (3, 2, 3000), (1, 4, 1000)):
        g = _table(people, bots, base=base)
        start(g, random.Random(people))
        g.winner, g.phase = "town", Phase.FINISHED
        for p in g.players:
            p.faction = "town"  # everyone on the winning side, so the comparison is fair
        await app.persist(g)
        await app.record_stats(g)
    full, half, solo = (await app.store.get_account(5000)), (await app.store.get_account(3000)), (
        await app.store.get_account(1000))
    assert full["games"] == half["games"] == solo["games"] == 1
    from tezmafia.shop import PLAY_COINS, WIN_COINS

    assert full["coins"] >= PLAY_COINS + WIN_COINS and full["gems"] >= 1  # game reward (plus any quests)
    assert half["coins"] == (PLAY_COINS + WIN_COINS) // 2 and half["gems"] == 0  # half, no quests, no gems
    assert solo["coins"] == 0 and solo["xp"] > 0 and solo["gems"] == 0  # XP only
    week = {uid for uid, _, _ in await app.store.week_top(week_key(), limit=50)}
    assert 5000 in week and 3000 not in week and 1000 not in week  # no tournament points with bots
    season = {name for name, _, _ in await app.store.season_top(time.strftime("%Y-%m"), limit=50)}
    assert "P5000" in season and "P3000" not in season
    for uid in (-1, -2):
        assert (await app.store.get_account(uid))["games"] == 0  # bots never get a stats row
    cards = [c for c in app.bot.calls if c[0] == "send_photo"]
    assert cards and all(c[1][0] > 0 for c in cards)
    assert any(t("uz", "bot.reward_note", humans=3) in c[2]["caption"] for c in cards)
    assert await app.store.achievement_count(1000) == 0  # no achievements farmed against bots


@pytest.mark.asyncio
async def test_addbot_is_for_the_host_and_fills_the_lobby(app: App) -> None:
    g = _table(1, 0)
    await app.persist(g)
    sent: list[str] = []

    def msg(uid: int) -> FakeMsg:
        m = FakeMsg(User(id=uid, is_bot=False, first_name="U"), Chat(id=-100, type=ChatType.SUPERGROUP), "/addbot", app.bot)
        m.answer = AsyncMock(side_effect=lambda text, **k: sent.append(text))  # type: ignore[method-assign]
        return m

    await botmod.cmd_addbot(msg(555), SimpleNamespace(args="4"))  # type: ignore[arg-type]
    assert sent[-1] == t("uz", "next.host_only")
    await botmod.cmd_addbot(msg(100), SimpleNamespace(args="4"))  # type: ignore[arg-type]
    lobby = await app.store.active_in_chat(-100)
    assert len(lobby.players) == 5 and sum(is_bot(p.user_id) for p in lobby.players) == 4


@pytest.mark.asyncio
async def test_a_full_game_with_bots_runs_to_the_end(app: App) -> None:
    """One person and four bots through the real App phases (night, vote, lynch) until it ends."""
    app.dm = AsyncMock(return_value=True)  # type: ignore[method-assign]
    g = _table(1, 4)
    await app.persist(g)
    async with app.game_lock(g.id):
        await app.start_game(await app.store.load(g.id))
    steps = {
        Phase.NIGHT: app._timed_resolve_night,
        Phase.DAY: app._timed_begin_vote,
        Phase.VOTING: app._timed_resolve_vote,
        Phase.LYNCH: app._timed_resolve_lynch,
    }
    for _ in range(60):
        game = await app.store.load(g.id)
        if game.phase == Phase.FINISHED:
            break
        await steps[game.phase](g.id)
    final = await app.store.load(g.id)
    assert final.phase == Phase.FINISHED and final.winner
    assert (await app.store.get_account(100))["games"] == 1
