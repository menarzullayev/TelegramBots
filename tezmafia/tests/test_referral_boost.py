"""Referral boost: tiered inviter rewards, monthly recruiters ranking and traffic-source tracking."""

from __future__ import annotations

import asyncio
import sqlite3
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.enums import ChatType
from aiogram.types import Chat, User
from sqlalchemy import text

from tests.test_bot_e2e import FakeBot, FakeMsg, _ready_game, _settings
from tezmafia import bot as botmod
from tezmafia import texts
from tezmafia.bot import App
from tezmafia.db import Store
from tezmafia.engine import Phase, start
from tezmafia.i18n import t
from tezmafia.retention import (
    REF_INVITER_COINS,
    REF_NEW_COINS,
    REF_TIERS,
    normalize_source,
)
from tezmafia.shop import SPECIAL_BADGES
from tezmafia.social import week_key

OWNER = 1
INVITER = 7


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


async def _qualify(app: App, referrer: int, n: int, base: int = 1000) -> None:
    """n brand-new players invited by `referrer`, each paid out as if they finished a first full game."""
    for i in range(base, base + n):
        assert await app.store.add_referral(i, referrer)
        await app.reward_referral(i, f"New{i}")


async def _set_rewarded_at(app: App, user_id: int, when: float) -> None:
    async with app.store.session() as s:
        await s.execute(text("UPDATE referrals SET rewarded_at = :t WHERE user_id = :u"), {"t": when, "u": user_id})
        await s.commit()


def _month_start(offset: int = 0) -> float:
    now = time.localtime()
    month = now.tm_mon - 1 + offset
    return time.mktime((now.tm_year + month // 12, month % 12 + 1, 1, 12, 0, 0, 0, 0, -1))


def _month_key(offset: int = 0) -> str:
    return time.strftime("%Y-%m", time.localtime(_month_start(offset)))


# --- tiers ---------------------------------------------------------------------------------------


def test_new_player_gets_fifty_coins_in_total() -> None:
    assert REF_NEW_COINS == 50 and REF_INVITER_COINS == 50


@pytest.mark.asyncio
async def test_each_tier_pays_exactly_once(app: App) -> None:
    expected = {1: (50, 1), 3: (50 * 3 + 150, 1), 10: (50 * 10 + 150 + 300, 1 + 3), 25: (50 * 25 + 150 + 300 + 700, 1 + 3 + 8)}
    done = 0
    for target, (coins, gems) in expected.items():
        await _qualify(app, INVITER, target - done, base=1000 + done)
        done = target
        acc = await app.store.get_account(INVITER)
        assert (acc["coins"], acc["gems"]) == (coins, gems), target
        assert await app.store.claim_ref_tiers(INVITER) == []  # asking again pays nothing
        assert await app.store.claim_ref_tiers(INVITER) == []
    assert (await app.store.get_account(INVITER))["coins"] == 2400
    assert await app.reward_referral(1000, "New1000") is None  # an already rewarded invite pays nothing more
    assert (await app.store.get_account(INVITER))["coins"] == 2400
    assert await app.store.qualified_count(INVITER) == 25


@pytest.mark.asyncio
async def test_tier_three_grants_the_wearable_recruiter_badge_and_tier_25_the_title(app: App) -> None:
    await _qualify(app, INVITER, 2)
    assert "recruiter" not in await app.store.owned_badges(INVITER)
    await _qualify(app, INVITER, 1, base=2000)
    emoji = SPECIAL_BADGES["recruiter"][0]
    assert emoji == "🤝" and "recruiter" in await app.store.owned_badges(INVITER)
    assert (await app.store.get_account(INVITER))["badge"] == emoji  # worn, nothing else was
    await app.store.take_off_badge(INVITER)
    assert await app.store.buy_badge(INVITER, "Inv", "recruiter") == "owned"  # wearable like trophy/founder
    assert (await app.store.get_account(INVITER))["badge"] == emoji
    assert not await app.store.has_ref_title(INVITER)
    assert "Qorashahar recruiter" not in texts.profile_text("Inv", 0, 0, recruiter=False)
    await _qualify(app, INVITER, 22, base=3000)
    assert await app.store.has_ref_title(INVITER)
    assert "Qorashahar recruiter" in texts.profile_text("Inv", 0, 0, recruiter=True)


@pytest.mark.asyncio
async def test_a_worn_badge_is_not_replaced_by_the_recruiter_badge(app: App) -> None:
    await app.store.credit_wallet(INVITER, "Inv", gems=12)
    assert await app.store.buy_badge(INVITER, "Inv", "crown") == "bought"
    await _qualify(app, INVITER, 3)
    assert (await app.store.get_account(INVITER))["badge"] == "👑"
    assert "recruiter" in await app.store.owned_badges(INVITER)


@pytest.mark.asyncio
async def test_concurrent_claims_pay_a_tier_once(app: App) -> None:
    for i in range(1000, 1003):
        assert await app.store.add_referral(i, INVITER)
        assert await app.store.take_referral(i) == INVITER  # qualified, tiers not claimed yet
    results = await asyncio.gather(*(app.store.claim_ref_tiers(INVITER) for _ in range(6)))
    paid = [tier.invites for batch in results for tier in batch]
    assert sorted(paid) == [1, 3]
    acc = await app.store.get_account(INVITER)
    assert (acc["coins"], acc["gems"]) == (150, 1)


@pytest.mark.asyncio
async def test_concurrent_rewards_for_the_same_invitee_pay_once(app: App) -> None:
    assert await app.store.add_referral(1000, INVITER)
    await asyncio.gather(*(app.reward_referral(1000, "New") for _ in range(4)))
    acc = await app.store.get_account(INVITER)
    assert (acc["coins"], acc["gems"]) == (REF_INVITER_COINS, 1)


@pytest.mark.asyncio
async def test_unqualified_referrals_do_not_count(app: App) -> None:
    for i in range(1000, 1010):
        assert await app.store.add_referral(i, INVITER)  # arrived, never finished a full game
    assert await app.store.referral_count(INVITER) == 10
    assert await app.store.qualified_count(INVITER) == 0
    assert await app.store.claim_ref_tiers(INVITER) == []
    acc = await app.store.get_account(INVITER)
    assert (acc["coins"], acc["gems"]) == (0, 0)
    assert await app.store.recruiter_top(_month_key()) == []
    assert await app.store.claim_ref_tiers(-5) == []  # a bot seat never earns tiers


@pytest.mark.asyncio
async def test_inviter_dm_names_the_tier(app: App) -> None:
    await _qualify(app, INVITER, 1)
    text_ = app.dm.await_args.args[1]
    assert t("uz", "invite.reward", name="New1000", coins=REF_INVITER_COINS) in text_
    assert t("uz", "invite.tier", n=1, count=1, rewards=texts.tier_rewards(REF_TIERS[0], "uz")) in text_
    await _qualify(app, INVITER, 1, base=2000)  # second invite reaches no tier
    assert "🎁" not in app.dm.await_args.args[1]


@pytest.mark.asyncio
async def test_invite_shows_progress(app: App) -> None:
    await _qualify(app, INVITER, 1)
    sent: list[str] = []
    msg = FakeMsg(User(id=INVITER, is_bot=False, first_name="I"), Chat(id=INVITER, type=ChatType.PRIVATE), "/invite", app.bot)
    msg.answer = AsyncMock(side_effect=lambda text_, **k: sent.append(text_))  # type: ignore[method-assign]
    await botmod.cmd_invite(msg)  # type: ignore[arg-type]
    assert t("uz", "invite.progress", q=1, next=3, rewards=texts.tier_rewards(REF_TIERS[1], "uz")) in sent[0]


# --- migration -----------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_existing_database_is_migrated(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    path = tmp_path / "data" / "old.db"
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE referrals (user_id BIGINT PRIMARY KEY, referrer_id BIGINT, at FLOAT, rewarded INTEGER DEFAULT 0)"
    )
    con.executemany(
        "INSERT INTO referrals VALUES (?, ?, ?, ?)", [(1, 7, 1000.0, 1), (2, 7, 2000.0, 0)]
    )
    con.commit()
    con.close()
    store = Store(f"sqlite+aiosqlite:///{path}")
    await store.init()
    await store.init()  # running the migration twice is harmless
    async with store.session() as s:
        rows = (await s.execute(text("SELECT user_id, rewarded, rewarded_at FROM referrals ORDER BY user_id"))).all()
    assert [tuple(r) for r in rows] == [(1, 1, 1000.0), (2, 0, None)]
    await store.engine.dispose()


# --- monthly recruiters --------------------------------------------------------------------------


async def _month_fixture(app: App) -> None:
    """A: 3 invites, B: 3 (but reached 3 later), C: 2, D: 1 (hidden below), bot: 5, last month: E 9."""
    plan = {10: 3, 11: 3, 12: 2, 13: 1, -5: 5, 14: 9}
    uid = 5000
    for referrer, n in plan.items():
        for k in range(n):
            uid += 1
            assert await app.store.add_referral(uid, referrer)
            assert await app.store.take_referral(uid) == referrer
            if referrer == 14:
                when = _month_start(-1) + k
            elif referrer == 11:
                when = _month_start() + 3600 * 10 + k  # B's last invite is later than A's
            else:
                when = _month_start() + 3600 + k
            await _set_rewarded_at(app, uid, when)
    for u, name in ((10, "Ann"), (11, "Bob"), (12, "Cy"), (13, "Di"), (14, "Eve")):
        await app.store.credit_wallet(u, name, coins=0)


@pytest.mark.asyncio
async def test_monthly_leaderboard_order_ties_and_exclusions(app: App) -> None:
    await _month_fixture(app)
    top = await app.store.recruiter_top(_month_key())
    assert [(u, n) for u, _name, n, _t in top] == [(10, 3), (11, 3), (12, 2), (13, 1)]  # tie: earlier finisher first
    assert all(u > 0 for u, *_ in top)  # the bot seat never shows
    assert 14 not in [u for u, *_ in top]  # last month's invites stay out of this month
    assert [u for u, *_ in await app.store.recruiter_top(_month_key(-1))] == [14]
    await app.store.set_recruiter_hidden(10, True)
    assert 10 not in [u for u, *_ in await app.store.recruiter_top(_month_key())]
    assert await app.store.recruiter_hidden(10)
    await app.store.set_recruiter_hidden(10, False)
    assert [u for u, *_ in await app.store.recruiter_top(_month_key())][0] == 10
    assert len(await app.store.recruiter_top(_month_key(), limit=2)) == 2


@pytest.mark.asyncio
async def test_top_view_lists_recruiters_with_the_title(app: App) -> None:
    await _month_fixture(app)
    async with app.store.session() as s:
        await s.execute(text("INSERT INTO referral_tiers (user_id, tier, at) VALUES (10, 25, 0)"))
        await s.commit()
    view = await botmod._top_view("recruit", 1, "uz")
    assert t("uz", "top.recruit", month=_month_key()) in view and "Ann 🤝 Qorashahar recruiter" in view
    assert "Bob —" in view and "Qorashahar recruiter" not in view.split("Bob")[1]
    from tezmafia.keyboards import top_kb

    for in_group in (True, False):
        data = [b.callback_data for row in top_kb("recruit", in_group).inline_keyboard for b in row]
        assert "top:recruit" in data


@pytest.mark.asyncio
async def test_month_prizes_are_paid_once(app: App) -> None:
    await _month_fixture(app)
    month = _month_key()
    assert await app.award_recruiters(month) == [10, 11]  # Cy is third but has 2 invites, under the minimum of 3
    for uid, gems in ((10, 3), (11, 2), (12, 0), (13, 0)):
        assert (await app.store.get_account(uid))["gems"] == gems
    assert "recruiter_month" in await app.store.owned_badges(10)
    assert (await app.store.get_account(10))["badge"] == SPECIAL_BADGES["recruiter_month"][0] == "🏅"
    assert "recruiter_month" not in await app.store.owned_badges(11)
    assert app.dm.await_count == 2
    assert await app.award_recruiters(month) == []  # a second run, e.g. after a restart, pays nothing
    assert await app.award_recruiters(month) == []
    assert (await app.store.get_account(10))["gems"] == 3 and app.dm.await_count == 2


@pytest.mark.asyncio
async def test_hidden_recruiters_are_not_paid(app: App) -> None:
    await _month_fixture(app)
    await app.store.set_recruiter_hidden(10, True)
    assert await app.award_recruiters(_month_key()) == [11]  # Cy (2) and Di (1) are under the minimum
    assert (await app.store.get_account(10))["gems"] == 0
    assert (await app.store.get_account(11))["gems"] == 3
    assert "recruiter_month" in await app.store.owned_badges(11)


@pytest.mark.asyncio
async def test_default_month_is_the_previous_one(app: App, monkeypatch) -> None:
    await _month_fixture(app)
    assert await app.award_recruiters() == [14]  # last month's only recruiter
    assert await app.award_recruiters() == []
    assert (await app.store.get_account(14))["gems"] == 3


@pytest.mark.asyncio
async def test_settings_toggle_hides_and_shows_the_player(app: App) -> None:
    edit = AsyncMock()
    answered: list[str] = []
    query = SimpleNamespace(
        from_user=SimpleNamespace(id=INVITER),
        message=SimpleNamespace(chat=SimpleNamespace(id=INVITER, type=ChatType.PRIVATE), edit_reply_markup=edit),
        answer=AsyncMock(side_effect=lambda text_="", **k: answered.append(text_)),
    )
    await botmod.cb_recruiter_toggle(query)  # type: ignore[arg-type]
    assert await app.store.recruiter_hidden(INVITER) and answered[-1] == t("uz", "recruit.hidden_on")
    assert edit.await_args.kwargs["reply_markup"].inline_keyboard[-1][0].text == t("uz", "btn.recruit_hidden")
    await botmod.cb_recruiter_toggle(query)  # type: ignore[arg-type]
    assert not await app.store.recruiter_hidden(INVITER) and answered[-1] == t("uz", "recruit.hidden_off")
    query.message.chat.type = ChatType.GROUP  # the toggle is private-chat only
    await botmod.cb_recruiter_toggle(query)  # type: ignore[arg-type]
    assert not await app.store.recruiter_hidden(INVITER)


# --- traffic source ------------------------------------------------------------------------------


def test_source_normalization() -> None:
    assert normalize_source("") == "direct"
    assert normalize_source("ref_123") == "ref"
    assert normalize_source("ad_uz1") == "ad_uz1"
    assert normalize_source("AD_UZ1") == "ad_uz1"
    assert normalize_source("g_abc123") == "game"
    assert normalize_source("a" * 80) == "a" * 32
    assert normalize_source("x';DROP TABLE stats;--<b>") == "xdroptablestats--b"  # only [A-Za-z0-9_-] survives
    assert normalize_source("<>;'\"") == "direct"
    assert normalize_source("ref_12;x") == "ref_12x"  # not a real referral payload: treated as a plain tag


async def _start(app: App, uid: int, payload: str | None) -> list[str]:
    sent: list[str] = []
    msg = FakeMsg(User(id=uid, is_bot=False, first_name="N"), Chat(id=uid, type=ChatType.PRIVATE), "/start", app.bot)
    msg.answer = AsyncMock(side_effect=lambda text_, **k: sent.append(text_))  # type: ignore[method-assign]
    await botmod.cmd_start(msg, SimpleNamespace(args=payload))  # type: ignore[arg-type]
    return sent


async def _source_of(app: App, uid: int) -> str | None:
    async with app.store.session() as s:
        return (await s.execute(text("SELECT source FROM user_sources WHERE user_id = :u"), {"u": uid})).scalar_one_or_none()


@pytest.mark.asyncio
async def test_source_is_stored_on_the_first_start_only(app: App) -> None:
    await _start(app, 201, "ad_uz1")
    assert await _source_of(app, 201) == "ad_uz1"
    await _start(app, 201, "ad_other")  # later /start with another payload changes nothing
    await _start(app, 201, None)
    assert await _source_of(app, 201) == "ad_uz1"
    await _start(app, 202, None)
    assert await _source_of(app, 202) == "direct"
    sent = await _start(app, 203, "ref_7")  # referral registration keeps working
    assert await _source_of(app, 203) == "ref" and sent[0] == t("uz", "invite.welcome", coins=REF_NEW_COINS)
    assert await app.store.referral_count(7) == 1
    await app.store.credit_wallet(204, "Old", coins=1)  # an existing player is not a new source
    await _start(app, 204, "ad_uz1")
    assert await _source_of(app, 204) is None


@pytest.mark.asyncio
async def test_malicious_payload_is_sanitized_and_harmless(app: App) -> None:
    await _start(app, 301, "x'); DROP TABLE user_sources;--" + "Z" * 100)
    source = await _source_of(app, 301)
    assert source and len(source) <= 32 and set(source) <= set("abcdefghijklmnopqrstuvwxyz0123456789_-")
    async with app.store.session() as s:
        assert (await s.execute(text("SELECT COUNT(*) FROM user_sources"))).scalar_one() == 1
    await _start(app, 302, "<script>")
    assert await _source_of(app, 302) == "script"
    await _start(app, 303, "ref_")  # empty-id referral link
    assert await _source_of(app, 303) == "ref_"


@pytest.mark.asyncio
async def test_start_in_a_group_records_no_source(app: App, monkeypatch) -> None:
    monkeypatch.setattr(botmod, "cmd_mafia", AsyncMock())
    msg = FakeMsg(User(id=401, is_bot=False, first_name="N"), Chat(id=-100, type=ChatType.SUPERGROUP), "/start", app.bot)
    await botmod.cmd_start(msg, SimpleNamespace(args="ad_uz1"))  # type: ignore[arg-type]
    assert await _source_of(app, 401) is None


@pytest.mark.asyncio
async def test_source_funnel_counts_per_source(app: App) -> None:
    g = _ready_game(5)
    g.chat_id = -5
    start(g)
    g.winner, g.phase = "town", Phase.FINISHED
    ids = [p.user_id for p in g.players]
    for uid in ids[:3]:
        await _start(app, uid, "ad_uz1")
    await _start(app, ids[3], "ad_uz1")
    await _start(app, 900, "ad_uz1")  # never plays
    await _start(app, ids[4], None)
    await _start(app, 901, "blog")
    await app.record_stats(g)
    rows = await app.store.source_funnel(time.time() - 60)
    assert rows[0] == {"source": "ad_uz1", "new": 5, "played": 4, "full": 4}
    assert {"source": "direct", "new": 1, "played": 1, "full": 1} in rows
    assert {"source": "blog", "new": 1, "played": 0, "full": 0} in rows
    assert await app.store.source_funnel(time.time() + 60) == []  # nothing arrived after "now"


@pytest.mark.asyncio
async def test_weekly_digest_has_a_source_section_for_the_owner(app: App) -> None:
    app.settings.owner_id = OWNER
    await _start(app, 501, "ad_uz1")
    await _start(app, 502, "ad_uz1")
    report = await app.weekly_digest(week_key(), post=False)
    assert t("uz", "funnel.sources") in report
    assert t("uz", "funnel.source_row", source="ad_uz1", new=2, played=0, full=0) in report
    sent: list[str] = []
    msg = FakeMsg(User(id=OWNER, is_bot=False, first_name="O"), Chat(id=OWNER, type=ChatType.PRIVATE), "/weekly", app.bot)
    msg.answer = AsyncMock(side_effect=lambda text_, **k: sent.append(text_))  # type: ignore[method-assign]
    await botmod.cmd_weekly(msg, SimpleNamespace(args=None))  # type: ignore[arg-type]
    assert len(sent) == 1 and "ad_uz1" in sent[0]


@pytest.mark.asyncio
async def test_weekly_sources_are_not_shown_to_other_users(app: App) -> None:
    app.settings.owner_id = OWNER
    await _start(app, 501, "ad_uz1")
    sent: list[str] = []
    msg = FakeMsg(User(id=2, is_bot=False, first_name="U"), Chat(id=2, type=ChatType.PRIVATE), "/weekly", app.bot)
    msg.answer = AsyncMock(side_effect=lambda text_, **k: sent.append(text_))  # type: ignore[method-assign]
    await botmod.cmd_weekly(msg, SimpleNamespace(args="post"))  # type: ignore[arg-type]
    assert sent == [] and app.dm.await_count == 0
    # the public channel digest never carries the source section either
    assert t("uz", "funnel.sources") not in texts.weekly_digest(week_key(), 0, 0, [], [], "uz")


@pytest.mark.asyncio
async def test_empty_source_section_says_so(app: App) -> None:
    report = await app.weekly_digest(week_key(), post=False)
    assert t("uz", "funnel.sources_empty") in report


@pytest.mark.asyncio
async def test_delete_user_erases_source_and_preference(app: App) -> None:
    await _start(app, 601, "ad_uz1")
    await app.store.set_recruiter_hidden(601, True)
    await app.store.delete_user(601)
    assert await _source_of(app, 601) is None and not await app.store.recruiter_hidden(601)


@pytest.mark.asyncio
async def test_mini_app_state_has_recruiters_and_title(app: App) -> None:
    from tezmafia.webapp.server import build_state

    await _month_fixture(app)
    async with app.store.session() as s:
        await s.execute(text("INSERT INTO referral_tiers (user_id, tier, at) VALUES (10, 25, 0)"))
        await s.commit()
    state = await build_state(app, {"id": 10, "first_name": "Ann"})
    assert state["profile"]["title"] == "Qorashahar recruiter"
    assert state["recruiters"]["rows"][0] == {"name": "Ann 🤝 Qorashahar recruiter", "n": 3, "me": True}
    assert (await build_state(app, {"id": 11, "first_name": "Bob"}))["profile"]["title"] == ""
