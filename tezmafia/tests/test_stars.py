"""F4: Telegram Stars purchases, VIP subscription, refunds, gem badges, atomic wallet."""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import Chat, User

from tests.test_bot_e2e import FakeBot, FakeMsg, _settings
from tezmafia import bot as botmod
from tezmafia.bot import App
from tezmafia.db import Store
from tezmafia.engine import join, new_game
from tezmafia.i18n import t
from tezmafia.keyboards import shop_kb
from tezmafia.shop import BADGES, PLAY_COINS, STAR_PACKS, VIP_PERIOD, VIP_STARS, WIN_COINS


@pytest.fixture
async def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    store = Store(f"sqlite+aiosqlite:///{tmp_path}/data/t.db")
    await store.init()
    application = App(_settings(), store, FakeBot())  # type: ignore[arg-type]
    application.alerts = SimpleNamespace(send=AsyncMock(return_value=True))  # type: ignore[assignment]
    botmod.app = application
    yield application
    await store.engine.dispose()


def _cb(data: str, user_id: int = 7, chat_type: str = ChatType.PRIVATE) -> SimpleNamespace:
    return SimpleNamespace(
        data=data,
        from_user=SimpleNamespace(id=user_id, first_name="U"),
        message=SimpleNamespace(chat=SimpleNamespace(type=chat_type), edit_text=AsyncMock()),
        answer=AsyncMock(),
    )


def test_shop_offers_packs_vip_and_gems() -> None:
    data = [b.callback_data for row in shop_kb().inline_keyboard for b in row]
    assert {f"st:{k}" for k in STAR_PACKS} <= set(data)
    assert "st:vip" in data and "m:gems" in data


@pytest.mark.asyncio
async def test_pack_sends_xtr_invoice_to_dm(app: App) -> None:
    app.bot.send_invoice = AsyncMock()  # type: ignore[attr-defined]
    q = _cb("st:c450")
    await botmod.cb_stars(q)  # type: ignore[arg-type]
    kw = app.bot.send_invoice.await_args.kwargs
    assert app.bot.send_invoice.await_args.args[0] == 7
    assert kw["currency"] == "XTR" and kw["payload"] == "c450:7"
    assert kw["prices"][0].amount == STAR_PACKS["c450"][0]


@pytest.mark.asyncio
async def test_pack_from_group_points_to_dm(app: App) -> None:
    app.bot.send_invoice = AsyncMock()  # type: ignore[attr-defined]
    q = _cb("st:c100", chat_type=ChatType.SUPERGROUP)
    await botmod.cb_stars(q)  # type: ignore[arg-type]
    assert q.answer.await_args.args[0] == t("uz", "stars.sent_dm")


@pytest.mark.asyncio
async def test_closed_dm_asks_to_start_the_bot(app: App) -> None:
    app.bot.send_invoice = AsyncMock(side_effect=TelegramForbiddenError(method=MagicMock(), message="blocked"))  # type: ignore[attr-defined]
    q = _cb("st:c100")
    await botmod.cb_stars(q)  # type: ignore[arg-type]
    assert q.answer.await_args.args[0] == t("uz", "stars.open_dm")


@pytest.mark.asyncio
async def test_vip_uses_a_30_day_subscription_link(app: App) -> None:
    app.bot.create_invoice_link = AsyncMock(return_value="https://t.me/$abc")  # type: ignore[attr-defined]
    app.bot.send_message = AsyncMock()  # type: ignore[method-assign]
    await botmod.cb_stars(_cb("st:vip"))  # type: ignore[arg-type]
    kw = app.bot.create_invoice_link.await_args.kwargs
    assert kw["subscription_period"] == VIP_PERIOD and kw["prices"][0].amount == VIP_STARS
    button = app.bot.send_message.await_args.kwargs["reply_markup"].inline_keyboard[0][0]
    assert button.url == "https://t.me/$abc"


def _checkout(payload: str, amount: int, user_id: int = 7, currency: str = "XTR") -> SimpleNamespace:
    return SimpleNamespace(
        invoice_payload=payload, total_amount=amount, currency=currency,
        from_user=SimpleNamespace(id=user_id), answer=AsyncMock(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "amount", "user", "ok"),
    [
        ("c100:7", 25, 7, True),
        ("vip:7", VIP_STARS, 7, True),
        ("c100:8", 25, 7, False),  # someone else's invoice
        ("c100:7", 1, 7, False),  # wrong amount
        ("gold:7", 25, 7, False),  # unknown product
    ],
)
async def test_pre_checkout_validates(app: App, payload: str, amount: int, user: int, ok: bool) -> None:
    q = _checkout(payload, amount, user)
    await botmod.on_pre_checkout(q)  # type: ignore[arg-type]
    assert q.answer.await_args.kwargs["ok"] is ok
    assert (q.answer.await_args.kwargs["error_message"] is None) is ok


def _paid_msg(payload: str, amount: int, charge: str, expires: int | None = None) -> FakeMsg:
    user = User(id=7, is_bot=False, first_name="U", username="u7")
    msg = FakeMsg(user, Chat(id=7, type=ChatType.PRIVATE), "", None)
    msg.successful_payment = SimpleNamespace(  # type: ignore[attr-defined]
        invoice_payload=payload, total_amount=amount, telegram_payment_charge_id=charge,
        subscription_expiration_date=expires,
    )
    msg.answer = AsyncMock()  # type: ignore[method-assign]
    return msg


@pytest.mark.asyncio
async def test_payment_credits_coins_exactly_once(app: App) -> None:
    msg = _paid_msg("c1200:7", 250, "ch-1")
    await botmod.on_paid(msg)  # type: ignore[arg-type]
    await botmod.on_paid(msg)  # replayed update
    assert (await app.store.get_account(7))["coins"] == 1200
    assert msg.answer.await_count == 1
    assert await app.store.stars_since(0) == (1, 250)
    assert "250⭐" in app.alerts.send.await_args.args[1]


@pytest.mark.asyncio
async def test_vip_payment_sets_expiry_and_bonus(app: App) -> None:
    expires = int(time.time()) + VIP_PERIOD
    await botmod.on_paid(_paid_msg("vip:7", VIP_STARS, "ch-v", expires))  # type: ignore[arg-type]
    assert (await app.store.get_account(7))["vip_until"] == expires
    await app.store.bump_stat(7, "U", won=True)
    base = PLAY_COINS + WIN_COINS
    assert (await app.store.get_account(7))["coins"] == base + base // 2
    assert await app.store.shown_badge(7) == "💎"


@pytest.mark.asyncio
async def test_refund_is_owner_only_and_takes_goods_back(app: App) -> None:
    await botmod.on_paid(_paid_msg("c450:7", 100, "ch-r"))  # type: ignore[arg-type]
    app.bot.refund_star_payment = AsyncMock()  # type: ignore[attr-defined]
    stranger = FakeMsg(User(id=99, is_bot=False, first_name="X"), Chat(id=99, type=ChatType.PRIVATE), "/refund ch-r", None)
    stranger.answer = AsyncMock()  # type: ignore[method-assign]
    await botmod.cmd_refund(stranger, SimpleNamespace(args="ch-r"))  # type: ignore[arg-type]
    app.bot.refund_star_payment.assert_not_awaited()
    assert (await app.store.get_account(7))["coins"] == 450

    owner = FakeMsg(User(id=1, is_bot=False, first_name="O"), Chat(id=1, type=ChatType.PRIVATE), "/refund ch-r", None)
    owner.answer = AsyncMock()  # type: ignore[method-assign]
    await botmod.cmd_refund(owner, SimpleNamespace(args="ch-r"))  # type: ignore[arg-type]
    app.bot.refund_star_payment.assert_awaited_once_with(7, "ch-r")
    assert (await app.store.get_account(7))["coins"] == 0
    assert await app.store.stars_since(0) == (0, 0)
    assert await app.store.refund("ch-r") is None  # cannot refund twice


@pytest.mark.asyncio
async def test_badges_cost_gems_once_and_can_be_removed(app: App) -> None:
    emoji, cost = BADGES["crown"]
    assert await app.store.buy_badge(7, "U", "crown") == "no_gems"
    await app.store.credit_wallet(7, "U", gems=cost + 1)
    assert await app.store.buy_badge(7, "U", "crown") == "bought"
    assert (await app.store.get_account(7))["gems"] == 1
    assert await app.store.buy_badge(7, "U", "crown") == "owned"
    assert (await app.store.get_account(7))["gems"] == 1
    assert await app.store.shown_badge(7) == emoji
    await app.store.take_off_badge(7)
    assert await app.store.shown_badge(7) == ""
    assert await app.store.buy_badge(7, "U", "nope") == "no_item"


@pytest.mark.asyncio
async def test_badge_callback_answers_and_redraws(app: App) -> None:
    q = _cb("gb:star")
    await botmod.cb_badge(q)  # type: ignore[arg-type]
    assert q.answer.await_args.args[0] == t("uz", "gems.no_gems")
    q.message.edit_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_joining_player_wears_badge(app: App) -> None:
    await app.store.credit_wallet(7, "U", gems=10)
    await app.store.buy_badge(7, "U", "rose")
    g = new_game(-1, 7)
    join(g, 7, "U", None)
    await botmod._wear_badge(g, 7)
    assert g.by_user(7).html_label().startswith("🌹 ")


@pytest.mark.asyncio
async def test_concurrent_wallet_updates_are_not_lost(app: App) -> None:
    await asyncio.gather(*(app.store.credit_wallet(7, "U", coins=5) for _ in range(20)))
    await asyncio.gather(*(app.store.bump_stat(7, "U", won=False) for _ in range(10)))
    assert (await app.store.get_account(7))["coins"] == 20 * 5 + 10 * PLAY_COINS
    assert (await app.store.get_account(7))["games"] == 10
