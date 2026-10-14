"""F3: Bot API 10.x features - ephemeral role reminder, disabled start, countdowns, rich summary, analytics."""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Chat

from tests.test_bot_e2e import FakeBot, _ready_game, _settings
from tezmafia import bot as botmod
from tezmafia import texts
from tezmafia.bot import App
from tezmafia.db import Store
from tezmafia.engine import Phase, begin_night, join, new_game, start
from tezmafia.i18n import t
from tezmafia.keyboards import lobby_kb, my_role_kb
from tezmafia.services.analytics import ActivityMiddleware, channel_of


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


def _role_query(game_id: str, user_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        id="cbq-1",
        data=f"me:{game_id}",
        from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(chat=Chat(id=-100, type=ChatType.SUPERGROUP)),
        answer=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_my_role_is_sent_as_ephemeral(app: App) -> None:
    g = _ready_game()
    start(g)
    await app.persist(g)
    app.bot.send_message = AsyncMock()  # type: ignore[method-assign]
    q = _role_query(g.id, 101)
    await botmod.cb_my_role(q)  # type: ignore[arg-type]
    kwargs = app.bot.send_message.await_args.kwargs
    eph = kwargs["ephemeral_message_parameters"]
    assert eph.receiver_user_id == 101 and eph.callback_query_id == "cbq-1"
    assert app.bot.send_message.await_args.args[0] == -100
    q.answer.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_my_role_falls_back_to_private_alert(app: App) -> None:
    g = _ready_game()
    start(g)
    await app.persist(g)
    app.bot.send_message = AsyncMock(side_effect=TelegramBadRequest(method=MagicMock(), message="no"))  # type: ignore[method-assign]
    q = _role_query(g.id, 101)
    await botmod.cb_my_role(q)  # type: ignore[arg-type]
    assert q.answer.await_args.kwargs["show_alert"] is True
    assert q.answer.await_args.args[0].startswith("🔒")


@pytest.mark.asyncio
async def test_my_role_refuses_spectators(app: App) -> None:
    g = _ready_game()
    start(g)
    await app.persist(g)
    app.bot.send_message = AsyncMock()  # type: ignore[method-assign]
    q = _role_query(g.id, 999)
    await botmod.cb_my_role(q)  # type: ignore[arg-type]
    app.bot.send_message.assert_not_awaited()
    assert q.answer.await_args.args[0] == t("uz", "role.not_playing")


def test_start_button_disabled_until_enough_players() -> None:
    g = new_game(-1, 1)
    join(g, 1, "A", None)
    btn = lobby_kb(g, "bot").inline_keyboard[1][0]
    assert btn.disabled is not None and btn.callback_data is None
    assert f"1/{g.min_players}" in btn.text
    for uid in range(2, g.min_players + 1):
        join(g, uid, f"P{uid}", None)
    btn = lobby_kb(g, "bot").inline_keyboard[1][0]
    assert btn.disabled is None and btn.callback_data == f"s:{g.id}"


def test_countdown_uses_date_time_entity() -> None:
    deadline = time.time() + 45
    text = texts.countdown(deadline)
    assert f'unix="{int(deadline)}"' in text and 'format="r"' in text
    assert texts.countdown(None) == ""
    g = _ready_game()
    begin_night(g, time.time(), 45)
    assert "<tg-time" in texts.night_group(g)


def test_night_and_day_banners_offer_role_button() -> None:
    g = _ready_game()
    kb = my_role_kb(g)
    assert kb.inline_keyboard[0][0].callback_data == f"me:{g.id}"


def test_rich_summary_is_a_table_with_every_player() -> None:
    g = _ready_game()
    start(g)
    g.winner = "mafia"
    html = texts.game_over_rich(g)
    assert html.count("<tr>") == len(g.players) + 1
    assert "<table bordered striped>" in html and "<tg-emoji" not in html


@pytest.mark.asyncio
async def test_summary_falls_back_to_text(app: App) -> None:
    g = _ready_game()
    start(g)
    g.winner = "town"
    app.bot.send_rich_message = AsyncMock(side_effect=TelegramBadRequest(method=MagicMock(), message="x"))  # type: ignore[attr-defined]
    sent: list[str] = []

    async def group(game, text, **k):
        sent.append(text)

    app.safe_group = group  # type: ignore[method-assign]
    await app.send_summary(g, "fallback")
    assert sent == ["fallback"]


def _member_update(old: str, new: str, chat_id: int = -100) -> SimpleNamespace:
    return SimpleNamespace(
        chat=Chat(id=chat_id, type=ChatType.SUPERGROUP),
        old_chat_member=SimpleNamespace(status=old),
        new_chat_member=SimpleNamespace(status=new),
    )


@pytest.mark.asyncio
async def test_added_to_group_sends_welcome_with_admin_hint(app: App) -> None:
    app.bot.send_message = AsyncMock()  # type: ignore[method-assign]
    await botmod.on_my_member(_member_update("left", "member"))  # type: ignore[arg-type]
    text = app.bot.send_message.await_args.args[1]
    assert t("uz", "group.welcome") in text and t("uz", "group.need_admin") in text
    app.bot.send_message.reset_mock()
    await botmod.on_my_member(_member_update("kicked", "administrator"))  # type: ignore[arg-type]
    assert t("uz", "group.need_admin") not in app.bot.send_message.await_args.args[1]


@pytest.mark.asyncio
async def test_removed_from_group_cancels_the_table(app: App) -> None:
    g = _ready_game()
    begin_night(g, time.time(), 45)
    await app.persist(g)
    await botmod.on_my_member(_member_update("member", "kicked"))  # type: ignore[arg-type]
    assert (await app.store.load(g.id)).phase == Phase.FINISHED


def test_channel_of_classifies_updates() -> None:
    dm = SimpleNamespace(
        message=SimpleNamespace(from_user=SimpleNamespace(id=1, is_bot=False), chat=SimpleNamespace(type="private")),
        callback_query=None, pre_checkout_query=None,
    )
    grp_cb = SimpleNamespace(
        message=None,
        callback_query=SimpleNamespace(from_user=SimpleNamespace(id=2), message=SimpleNamespace(chat=SimpleNamespace(type="supergroup"))),
        pre_checkout_query=None,
    )
    bot_msg = SimpleNamespace(
        message=SimpleNamespace(from_user=SimpleNamespace(id=3, is_bot=True), chat=SimpleNamespace(type="private")),
        callback_query=None, pre_checkout_query=None,
    )
    assert channel_of(dm) == (1, "dm")  # type: ignore[arg-type]
    assert channel_of(grp_cb) == (2, "group")  # type: ignore[arg-type]
    assert channel_of(bot_msg) is None  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_activity_counts_unique_users_per_channel(app: App) -> None:
    from aiogram.types import Update

    mw = ActivityMiddleware(app.store)
    handler = AsyncMock(return_value="ok")
    for uid, chat_type in [(1, "private"), (1, "private"), (2, "supergroup"), (1, "supergroup")]:
        upd = Update.model_validate(
            {
                "update_id": uid,
                "message": {
                    "message_id": 1, "date": 0, "text": "x",
                    "chat": {"id": uid if chat_type == "private" else -5, "type": chat_type},
                    "from": {"id": uid, "is_bot": False, "first_name": "U"},
                },
            }
        )
        assert await mw(handler, upd, {}) == "ok"
    today = time.strftime("%Y-%m-%d")
    assert await app.store.active_users(today) == 2
    assert await app.store.active_users(today, "dm") == 1
    assert await app.store.active_users(today, "group") == 2
    await app.store.delete_user(1)
    assert await app.store.active_users(today) == 1
