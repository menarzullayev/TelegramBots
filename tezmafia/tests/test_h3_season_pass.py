"""H3: monthly season pass — free and paid tracks, 20 tiers, starts 2026-11 (DECISION-17)."""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests.test_bot_e2e import FakeBot, _ready_game, _settings
from tezmafia import bot as botmod
from tezmafia import season_pass as sp
from tezmafia.bot import App
from tezmafia.db import Store
from tezmafia.engine import Phase, start
from tezmafia.i18n import t

SEASON = time.strftime("%Y-%m")


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


def test_ladder_rules() -> None:
    assert sp.PASS_START == "2026-11" and not sp.active("2026-10") and sp.active("2026-11") and sp.active("2027-01")
    assert [sp.tier_of(x) for x in (0, 99, 100, 1999, 2000, 99999)] == [0, 0, 1, 19, 20, 20]
    assert sp.reward("free", 3) == {"coins": 15} and sp.reward("free", 5) == {"coins": 15, "gems": 1}
    assert sp.reward("paid", 10) == {"skin": 1} and sp.reward("paid", 20) == {"gems": 5, "badge": 1}
    assert sp.claimable(250, False, set()) == ["f1", "f2"]
    assert sp.claimable(250, True, {"f1"}) == ["f2", "p1", "p2"]
    full = sp.total([f"f{n}" for n in range(1, 21)] + [f"p{n}" for n in range(1, 21)])
    # paid: 10 odd tiers pay coins, 8 even tiers pay gems, tier 10 a skin, tier 20 gems + badge
    assert full == {"coins": 20 * 15 + 10 * 30, "gems": 4 + 8 * 2 + 5, "skin": 1, "badge": 1}


@pytest.mark.asyncio
async def test_no_pass_before_the_start(app: App, monkeypatch) -> None:
    monkeypatch.setattr(sp, "PASS_START", "2999-01")
    g = _ready_game(5)
    start(g)
    g.winner, g.phase = "town", Phase.FINISHED
    await app.record_stats(g)
    assert await app.store.pass_state(SEASON, 100) == (0, False, set())
    text, kb = await botmod._pass_view(100, "uz")
    assert text == t("uz", "pass.soon", season="2999-01") and kb is None


@pytest.mark.asyncio
async def test_games_feed_pass_xp_and_claims_pay_once(app: App, monkeypatch) -> None:
    monkeypatch.setattr(sp, "PASS_START", SEASON)
    for _ in range(4):
        g = _ready_game(5)
        start(g)
        g.winner, g.phase = "town", Phase.FINISHED
        await app.record_stats(g)
    xp, premium, taken = await app.store.pass_state(SEASON, 100)
    assert xp >= 4 * 10 and not premium and taken == set()
    async with app.store.engine.begin() as conn:  # jump to tier 12 for the test
        from sqlalchemy import text

        await conn.execute(text("UPDATE pass_progress SET xp = 1250 WHERE user_id = 100"))
    before = await app.store.get_account(100)
    got = await app.store.claim_pass(SEASON, 100, "P0")
    assert got["ids"] == [f"f{n}" for n in range(1, 13)] and got["coins"] == 12 * 15 and got["gems"] == 2
    after = await app.store.get_account(100)
    assert after["coins"] - before["coins"] == 180 and after["gems"] - before["gems"] == 2
    assert (await app.store.claim_pass(SEASON, 100, "P0"))["ids"] == []  # nothing twice

    await app.store.set_pass_premium(SEASON, 100)
    got = await app.store.claim_pass(SEASON, 100, "P0")
    assert got["ids"] == [f"p{n}" for n in range(1, 13)]
    assert got["skin"] == "noir" and (await app.store.skins_of(100))[1] == ["noir"]  # tier 10 skin, not worn
    assert got["coins"] == 6 * 30 and got["gems"] == 5 * 2


@pytest.mark.asyncio
async def test_tier_20_badge_and_skin_fallback(app: App, monkeypatch) -> None:
    monkeypatch.setattr(sp, "PASS_START", SEASON)
    await app.store.credit_wallet(7, "A", coins=1)
    for key in ("noir", "gold", "neon"):
        await app.store.grant_skin(7, key)
    await app.store.set_pass_premium(SEASON, 7)
    async with app.store.engine.begin() as conn:
        from sqlalchemy import text

        await conn.execute(text("UPDATE pass_progress SET xp = 5000 WHERE user_id = 7"))
    got = await app.store.claim_pass(SEASON, 7, "A")
    assert got["badge"] and got["skin"] == ""  # all skins owned: paid in gems instead
    assert got["gems"] == 4 + 8 * 2 + 5 + 10
    assert "pass" in await app.store.owned_badges(7)


@pytest.mark.asyncio
async def test_paid_track_purchase_and_refund(app: App, monkeypatch) -> None:
    monkeypatch.setattr(sp, "PASS_START", SEASON)
    app.alerts.send = AsyncMock()  # type: ignore[method-assign]
    q = SimpleNamespace(from_user=SimpleNamespace(id=7), invoice_payload=f"pass:7:{SEASON}", currency="XTR",
                        total_amount=sp.PASS_STARS, answer=AsyncMock())
    await botmod.on_pre_checkout(q)  # type: ignore[arg-type]
    assert q.answer.await_args.kwargs["ok"] is True
    pay = SimpleNamespace(invoice_payload=f"pass:7:{SEASON}", telegram_payment_charge_id="px", total_amount=sp.PASS_STARS,
                          subscription_expiration_date=None)
    msg = SimpleNamespace(successful_payment=pay, from_user=SimpleNamespace(id=7, first_name="A", username=None),
                          answer=AsyncMock())
    await botmod.on_paid(msg)  # type: ignore[arg-type]
    assert (await app.store.pass_state(SEASON, 7))[1] is True
    msg.answer.assert_awaited_with(t("uz", "pass.paid", season=SEASON))
    await app.store.refund("px")
    assert (await app.store.pass_state(SEASON, 7))[1] is False


@pytest.mark.asyncio
async def test_pass_view_and_buttons(app: App, monkeypatch) -> None:
    monkeypatch.setattr(sp, "PASS_START", SEASON)
    await app.store.set_pass_premium(SEASON, 7)
    async with app.store.engine.begin() as conn:
        from sqlalchemy import text

        await conn.execute(text("UPDATE pass_progress SET xp = 230 WHERE user_id = 7"))
    text_, kb = await botmod._pass_view(7, "uz")
    assert t("uz", "pass.progress", tier=2, tiers=20, xp=230, left=70) in text_ and t("uz", "pass.premium_on") in text_
    buttons = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert buttons == ["ps:claim"]  # premium bought: no buy button
    answers: list[str] = []
    cq = SimpleNamespace(data="ps:claim", from_user=SimpleNamespace(id=7, first_name="A"), message=None,
                         answer=AsyncMock(side_effect=lambda text=None, **k: answers.append(text)))
    await botmod.cb_pass(cq)  # type: ignore[arg-type]
    assert answers[-1].startswith(t("uz", "pass.claimed", coins=30 + 30, gems=2, extra="")[:10])
    await botmod.cb_pass(cq)  # type: ignore[arg-type]
    assert answers[-1] == t("uz", "pass.nothing")
