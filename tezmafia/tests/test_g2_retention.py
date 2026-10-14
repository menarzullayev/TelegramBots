"""G2: daily bonus and streak, daily quests, referrals, scheduled games."""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.enums import ChatType
from aiogram.types import Chat, User

from tests.test_bot_e2e import FakeBot, FakeMsg, _ready_game, _settings
from tezmafia import bot as botmod
from tezmafia import texts
from tezmafia.bot import App
from tezmafia.db import Store
from tezmafia.engine import Phase, start
from tezmafia.i18n import t
from tezmafia.progress import Outcome
from tezmafia.retention import (
    QUESTS,
    REF_INVITER_COINS,
    REF_NEW_COINS,
    daily_reward,
    next_streak,
    quest_increments,
    todays_quests,
)


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


def test_daily_rewards_grow_and_cap() -> None:
    assert daily_reward(1) == (10, 0)
    assert daily_reward(2) == (15, 0)
    assert daily_reward(7) == (40, 1)
    assert daily_reward(30)[0] == 40


def test_streak_rules() -> None:
    assert next_streak("", "2026-10-14", "2026-10-13", 0) == 1
    assert next_streak("2026-10-13", "2026-10-14", "2026-10-13", 4) == 5
    assert next_streak("2026-10-10", "2026-10-14", "2026-10-13", 4) == 1  # broken streak
    assert next_streak("2026-10-14", "2026-10-14", "2026-10-13", 4) is None  # already taken


@pytest.mark.asyncio
async def test_daily_claim_once_per_day(app: App) -> None:
    first = await app.store.claim_daily(7, "Ann", "2026-10-14", "2026-10-13")
    assert first == {"streak": 1, "coins": 10, "gems": 0}
    assert await app.store.claim_daily(7, "Ann", "2026-10-14", "2026-10-13") is None
    second = await app.store.claim_daily(7, "Ann", "2026-10-15", "2026-10-14")
    assert second["streak"] == 2 and (await app.store.get_account(7))["coins"] == 25
    assert await app.store.streaks_at_risk("2026-10-15") == [(7, 2)]


def test_quests_are_the_same_for_everyone_each_day() -> None:
    day = "2026-10-14"
    assert todays_quests(day) == todays_quests(day) and len(set(todays_quests(day))) == 3
    assert set(todays_quests(day)) <= set(QUESTS)
    days = {tuple(todays_quests(f"2026-10-{d:02d}")) for d in range(1, 15)}
    assert len(days) > 3


def _outcome(**kw) -> Outcome:
    base = dict(role="citizen", faction="town", winner="town", won=True, alive=True, games=1, wins=1, xp=35)
    base.update(kw)
    return Outcome(**base)


@pytest.mark.asyncio
async def test_quest_progress_completes_once(app: App) -> None:
    assert await app.store.quest_advance("d", 7, {"play_2": 1}) == []
    assert await app.store.quest_advance("d", 7, {"play_2": 1, "win_1": 1}) == ["play_2", "win_1"]
    assert await app.store.quest_advance("d", 7, {"play_2": 1}) == []  # already done
    state = await app.store.quest_state("d", 7)
    assert state["play_2"] == (2, True)


def test_quest_increments_only_for_todays_quests() -> None:
    day = "2026-10-14"
    inc = quest_increments(day, _outcome(won=False, alive=False))
    assert set(inc) <= set(todays_quests(day))
    assert all(v > 0 for v in inc.values())


@pytest.mark.asyncio
async def test_finished_game_pays_quests(app: App, monkeypatch) -> None:
    monkeypatch.setattr("tezmafia.retention.todays_quests", lambda day: ["play_2", "win_1", "survive_1"])
    g = _ready_game()
    start(g)
    g.winner = "town"
    app.dm = AsyncMock(return_value=True)  # type: ignore[method-assign]
    await app.record_stats(g)
    town = next(p for p in g.players if p.faction == "town")
    acc = await app.store.get_account(town.user_id)
    assert acc["coins"] > 35  # game reward plus at least one quest
    state = await app.store.quest_state(time.strftime("%Y-%m-%d"), town.user_id)
    assert state["win_1"][1] is True


@pytest.mark.asyncio
async def test_referral_rules_and_reward(app: App) -> None:
    assert not await app.store.add_referral(7, 7)  # self-referral
    assert await app.store.add_referral(8, 7)
    assert not await app.store.add_referral(8, 9)  # referred once only
    await app.store.credit_wallet(9, "Old", coins=1)
    assert not await app.store.add_referral(9, 7)  # existing players cannot be referred
    await app.store.credit_wallet(7, "Inviter", coins=0)
    app.dm = AsyncMock(return_value=True)  # type: ignore[method-assign]
    await app.reward_referral(8, "New")
    await app.reward_referral(8, "New")  # second time pays nothing
    assert (await app.store.get_account(8))["coins"] == REF_NEW_COINS
    inviter = await app.store.get_account(7)
    assert inviter["coins"] == REF_INVITER_COINS
    assert inviter["name"] == "Inviter"  # crediting the inviter keeps their name
    assert await app.store.referral_count(7) == 1


@pytest.mark.asyncio
async def test_start_with_ref_payload_registers_referral(app: App) -> None:
    sent: list[str] = []
    msg = FakeMsg(User(id=55, is_bot=False, first_name="N"), Chat(id=55, type=ChatType.PRIVATE), "/start ref_7", app.bot)
    msg.answer = AsyncMock(side_effect=lambda text, **k: sent.append(text))  # type: ignore[method-assign]
    await botmod.cmd_start(msg, SimpleNamespace(args="ref_7"))  # type: ignore[arg-type]
    assert sent[0] == t("uz", "invite.welcome", coins=REF_NEW_COINS)
    assert await app.store.referral_count(7) == 1


def test_parse_hhmm() -> None:
    noon = time.mktime((2026, 10, 14, 12, 0, 0, 0, 0, -1))
    assert time.localtime(botmod._parse_hhmm("21:30", noon)).tm_hour == 21
    assert botmod._parse_hhmm("09:00", noon) > noon + 12 * 3600  # already passed today -> tomorrow
    for bad in ("", "25:00", "21", "aa:bb", "21:60"):
        assert botmod._parse_hhmm(bad, noon) is None


@pytest.mark.asyncio
async def test_schedule_reminds_then_opens_lobby(app: App) -> None:
    at = time.time() + 600
    sid = await app.store.create_schedule(-100, at, 100, "Host")
    assert await app.store.subscribe(sid, 101)
    dms: list[int] = []
    app.dm = AsyncMock(side_effect=lambda uid, text, **k: dms.append(uid) or True)  # type: ignore[method-assign]
    await app.scheduler_pass(now=at - 1200)  # too early
    assert dms == []
    await app.scheduler_pass(now=at - 600)  # inside the 15-minute window
    assert dms == [101]
    await app.scheduler_pass(now=at - 300)  # not reminded twice
    assert dms == [101]
    await app.scheduler_pass(now=at + 1)
    lobby = await app.store.active_in_chat(-100)
    assert lobby and lobby.phase == Phase.LOBBY and lobby.host_id == 100
    assert await app.store.open_schedules() == []


@pytest.mark.asyncio
async def test_schedule_is_admin_only_and_cancellable(app: App) -> None:
    chat = Chat(id=-100, type=ChatType.SUPERGROUP)
    user = User(id=5, is_bot=False, first_name="U")
    sent: list[str] = []
    msg = FakeMsg(user, chat, "/schedule 21:00", app.bot)
    msg.answer = AsyncMock(side_effect=lambda text, **k: sent.append(text))  # type: ignore[method-assign]
    await botmod.cmd_schedule(msg, SimpleNamespace(args="21:00"))  # type: ignore[arg-type]
    assert sent[-1] == t("uz", "config.admin_only")
    app.bot.get_chat_member = AsyncMock(return_value=SimpleNamespace(status="administrator"))  # type: ignore[method-assign]
    await botmod.cmd_schedule(msg, SimpleNamespace(args="21:00"))  # type: ignore[arg-type]
    assert len(await app.store.open_schedules()) == 1
    await botmod.cmd_schedule(msg, SimpleNamespace(args="off"))  # type: ignore[arg-type]
    assert await app.store.open_schedules() == []
    assert not await app.store.subscribe(1, 9)  # cancelled schedules take no subscribers


def test_quests_text_lists_three_quests() -> None:
    text = texts.quests_text("2026-10-14", {})
    assert text.count("/") >= 3 and t("uz", "quests.title") in text
