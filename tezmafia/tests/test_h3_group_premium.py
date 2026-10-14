"""H3: group premium — a Stars subscription any member pays for a group (DECISION-17)."""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.enums import ChatType
from aiogram.types import Chat, User

from tests.test_bot_e2e import FakeBot, FakeMsg, _ready_game, _settings
from tezmafia import bot as botmod
from tezmafia.bot import App
from tezmafia.db import Store
from tezmafia.engine import Phase, start
from tezmafia.i18n import t
from tezmafia.shop import GROUP_PREMIUM_STARS, PREMIUM_DAY_CHOICES

GROUP = -100


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


def _paid_message(user_id: int, payload: str, charge: str = "ch1", amount: int = GROUP_PREMIUM_STARS):
    pay = SimpleNamespace(
        invoice_payload=payload, telegram_payment_charge_id=charge, total_amount=amount,
        subscription_expiration_date=int(time.time()) + 30 * 86400,
    )
    msg = SimpleNamespace(successful_payment=pay, from_user=SimpleNamespace(id=user_id, first_name="Ali", username=None),
                          answer=AsyncMock())
    return msg


@pytest.mark.asyncio
async def test_pre_checkout_accepts_only_matching_premium(app: App) -> None:
    def query(uid: int, payload: str, amount: int = GROUP_PREMIUM_STARS):
        return SimpleNamespace(from_user=SimpleNamespace(id=uid), invoice_payload=payload, currency="XTR",
                               total_amount=amount, answer=AsyncMock())

    ok = query(7, f"gp:7:{GROUP}")
    await botmod.on_pre_checkout(ok)  # type: ignore[arg-type]
    assert ok.answer.await_args.kwargs["ok"] is True
    for bad in (query(8, f"gp:7:{GROUP}"), query(7, f"gp:7:{GROUP}", amount=1)):  # someone else's link, wrong price
        await botmod.on_pre_checkout(bad)  # type: ignore[arg-type]
        assert bad.answer.await_args.kwargs["ok"] is False


@pytest.mark.asyncio
async def test_payment_turns_premium_on_and_announces(app: App) -> None:
    app.alerts.send = AsyncMock()  # type: ignore[method-assign]
    app.bot.get_chat = AsyncMock(return_value=SimpleNamespace(title="Qora Shahar"))  # type: ignore[method-assign]
    assert await app.store.chat_premium(GROUP) is None
    msg = _paid_message(7, f"gp:7:{GROUP}")
    await botmod.on_paid(msg)  # type: ignore[arg-type]
    until, title = await app.store.chat_premium(GROUP)
    assert until > time.time() + 29 * 86400 and title == "Qora Shahar"
    assert any(c[0] == "send_message" and c[1][0] == GROUP for c in app.bot.calls)
    await botmod.on_paid(_paid_message(7, f"gp:7:{GROUP}"))  # replayed update: nothing twice
    assert sum(c[0] == "send_message" and c[1][0] == GROUP for c in app.bot.calls) == 1


@pytest.mark.asyncio
async def test_refund_ends_premium(app: App) -> None:
    app.alerts.send = AsyncMock()  # type: ignore[method-assign]
    app.bot.get_chat = AsyncMock(return_value=SimpleNamespace(title="G"))  # type: ignore[method-assign]
    await botmod.on_paid(_paid_message(7, f"gp:7:{GROUP}", charge="ch9"))  # type: ignore[arg-type]
    assert await app.store.chat_premium(GROUP)
    pay = await app.store.refund("ch9")
    assert pay and pay.product == "gp" and await app.store.chat_premium(GROUP) is None


@pytest.mark.asyncio
async def test_premium_unlocks_long_timers(app: App) -> None:
    app.bot.get_chat_member = AsyncMock(return_value=SimpleNamespace(status="administrator"))  # type: ignore[method-assign]
    msg = SimpleNamespace(chat=SimpleNamespace(id=GROUP), edit_text=AsyncMock())

    def query(data: str):
        return SimpleNamespace(data=data, from_user=SimpleNamespace(id=5), message=msg, answer=AsyncMock())

    seen = set()
    for _ in range(6):
        await botmod.cb_config(query("cfg:day"))  # type: ignore[arg-type]
        seen.add((await app.chat_cfg(GROUP))["day"])
    assert max(seen) == 120  # free groups stop at 120 s
    await app.store.set_chat_premium(GROUP, 7, time.time() + 86400, "G")
    for _ in range(6):
        await botmod.cb_config(query("cfg:day"))  # type: ignore[arg-type]
        seen.add((await app.chat_cfg(GROUP))["day"])
    assert max(seen) == max(PREMIUM_DAY_CHOICES)


@pytest.mark.asyncio
async def test_group_name_on_card_and_monthly_stats(app: App) -> None:
    app.dm = AsyncMock(return_value=True)  # type: ignore[method-assign]
    g = _ready_game(5)
    g.chat_id = GROUP
    start(g)
    g.winner, g.phase = "town", Phase.FINISHED
    await app.persist(g)
    await app.record_stats(g)
    footers = []
    import tezmafia.cards as cards

    real = cards.result_card
    cards.result_card = lambda *a, **k: (footers.append(a[5]), real(*a, **k))[1]  # type: ignore[assignment]
    try:
        await app.send_card(g, g.players[0], True, {"games": 1, "wins": 1, "xp": 40})
        await app.store.set_chat_premium(GROUP, 7, time.time() + 86400, "Qora Shahar")
        await app.send_card(g, g.players[0], True, {"games": 1, "wins": 1, "xp": 40})
    finally:
        cards.result_card = real  # type: ignore[assignment]
    assert "Qora Shahar" not in footers[0] and footers[1].startswith("Qora Shahar · ")

    sent: list[str] = []
    m = FakeMsg(User(id=5, is_bot=False, first_name="U"), Chat(id=GROUP, type=ChatType.SUPERGROUP), "/groupstats", app.bot)
    m.answer = AsyncMock(side_effect=lambda text, **k: sent.append(text))  # type: ignore[method-assign]
    await botmod.cmd_groupstats(m)  # type: ignore[arg-type]
    assert t("uz", "gs.months") in sent[-1] and time.strftime("%Y-%m") in sent[-1]
    await app.store.set_chat_premium(GROUP, 7, time.time() - 1, "Qora Shahar")  # expired (max() keeps the later date)
    async with app.store.engine.begin() as conn:
        from sqlalchemy import text

        await conn.execute(text("UPDATE chat_premium SET until = 1"))
    await botmod.cmd_groupstats(m)  # type: ignore[arg-type]
    assert t("uz", "gs.months") not in sent[-1]


@pytest.mark.asyncio
async def test_premium_command_and_link(app: App) -> None:
    sent: list[str] = []
    m = FakeMsg(User(id=5, is_bot=False, first_name="U"), Chat(id=GROUP, type=ChatType.SUPERGROUP), "/premium", app.bot)
    m.answer = AsyncMock(side_effect=lambda text, **k: sent.append(text))  # type: ignore[method-assign]
    await botmod.cmd_premium(m)  # type: ignore[arg-type]
    assert str(GROUP_PREMIUM_STARS) in sent[-1]
    app.bot.create_invoice_link = AsyncMock(return_value="https://t.me/$inv")  # type: ignore[method-assign]
    q = SimpleNamespace(data=f"gp:{GROUP}", from_user=SimpleNamespace(id=5),
                        message=SimpleNamespace(chat=SimpleNamespace(title="G")), answer=AsyncMock())
    await botmod.cb_premium(q)  # type: ignore[arg-type]
    kw = app.bot.create_invoice_link.await_args.kwargs
    assert kw["payload"] == f"gp:5:{GROUP}" and kw["subscription_period"] == 2592000
    assert kw["prices"][0].amount == GROUP_PREMIUM_STARS
    q.answer.assert_awaited_with(t("uz", "premium.link_sent"), show_alert=True)
