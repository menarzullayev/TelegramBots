"""F1 foundation: per-chat locks, timers that survive Telegram failures, permissions, plumbing."""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
from aiogram.types import Chat, User

from tests.test_bot_e2e import FakeBot, FakeMsg, _ready_game, _settings
from tezmafia import bot as botmod
from tezmafia.bot import App
from tezmafia.db import Store
from tezmafia.engine import Phase, begin_night, cancel, join, mark_dm_ok, new_game
from tezmafia.i18n import t
from tezmafia.services.runtime import Alerter, ChatLocks, InstanceLock, RetryAfterMiddleware


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


def _query(data: str, user: int = 100) -> SimpleNamespace:
    return SimpleNamespace(
        data=data,
        from_user=SimpleNamespace(id=user, first_name="U"),
        message=SimpleNamespace(chat=Chat(id=user, type=ChatType.PRIVATE)),
        answer=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_chat_locks_are_independent() -> None:
    locks = ChatLocks()
    async with locks(1):
        # Another chat is not blocked while chat 1 is busy.
        await asyncio.wait_for(locks(2).acquire(), timeout=0.5)
        locks(2).release()
        assert locks(1).locked()
    assert locks(1) is locks(1)


@pytest.mark.asyncio
async def test_timer_is_armed_even_if_telegram_fails(app: App, monkeypatch) -> None:
    g = _ready_game()
    await app.persist(g)

    async def broken(*a, **k):
        raise TelegramNetworkError(method=MagicMock(), message="down")

    monkeypatch.setattr(botmod, "apply_phase_mutes", broken)
    with pytest.raises(TelegramNetworkError):
        await app.enter_night(g)
    task = app.timers[g.id]
    assert not task.done()  # the night still ends on time


@pytest.mark.asyncio
async def test_watchdog_rearms_a_stuck_game(app: App) -> None:
    g = _ready_game()
    begin_night(g, time.time() - 600, 45)
    await app.persist(g)
    assert g.id not in app.timers
    assert await app.watchdog_pass() == [g.id]
    assert not app.timers[g.id].done()
    # A game with a live timer is left alone.
    assert await app.watchdog_pass() == []


@pytest.mark.asyncio
async def test_watchdog_ignores_games_still_in_time(app: App) -> None:
    g = _ready_game()
    begin_night(g, time.time(), 45)
    await app.persist(g)
    assert await app.watchdog_pass() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("data", ["v:", "v:abc", "v:g:x", "v:g:0", "v:g:-1", "ly:g:2", "vx:", "s:", "l:a:b"])
async def test_malformed_callbacks_are_answered_not_crashed(app: App, data: str) -> None:
    handler = {
        "v": botmod.cb_vote,
        "ly": botmod.cb_lynch,
        "vx": botmod.cb_vote_clear,
        "s": botmod.cb_start,
        "l": botmod.cb_leave,
    }[data.split(":")[0]]
    q = _query(data)
    await handler(q)  # type: ignore[arg-type]
    q.answer.assert_awaited()


@pytest.mark.asyncio
async def test_night_callback_rejects_bad_seat(app: App) -> None:
    q = _query("nm:g:zz")
    await botmod.cb_night(q)  # type: ignore[arg-type]
    q.answer.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_extend_is_host_only(app: App) -> None:
    chat = Chat(id=-100, type=ChatType.GROUP, title="G")
    g = new_game(-100, 100)
    join(g, 100, "Host", None)
    g.deadline = time.time() + 30
    await app.persist(g)
    stranger = User(id=555, is_bot=False, first_name="S")
    sent: list[str] = []
    msg = FakeMsg(stranger, chat, "/extend", app.bot)

    async def answer(text, **k):
        sent.append(text)

    msg.answer = answer  # type: ignore[method-assign]
    await botmod.cmd_extend(msg)  # type: ignore[arg-type]
    assert sent == [t("uz", "next.host_only")]
    assert (await app.store.load(g.id)).lobby_extends == 0


@pytest.mark.asyncio
async def test_deep_link_join_requires_group_membership(app: App) -> None:
    g = new_game(-100, 100)
    join(g, 100, "Host", None)
    await app.persist(g)
    app.bot.get_chat_member = AsyncMock(return_value=SimpleNamespace(status="left"))  # type: ignore[method-assign]
    outsider = User(id=777, is_bot=False, first_name="O")
    sent: list[str] = []
    msg = FakeMsg(outsider, Chat(id=777, type=ChatType.PRIVATE), f"/start g_{g.id}", app.bot)

    async def answer(text, **k):
        sent.append(text)

    msg.answer = answer  # type: ignore[method-assign]
    await botmod.cmd_start(msg, SimpleNamespace(args=f"g_{g.id}"))  # type: ignore[arg-type]
    assert sent == [t("uz", "start.not_member")]
    assert not (await app.store.load(g.id)).by_user(777)

    app.bot.get_chat_member = AsyncMock(return_value=SimpleNamespace(status="member"))  # type: ignore[method-assign]
    await botmod.cmd_start(msg, SimpleNamespace(args=f"g_{g.id}"))  # type: ignore[arg-type]
    assert (await app.store.load(g.id)).by_user(777)


@pytest.mark.asyncio
async def test_closed_dm_cancels_with_readable_text(app: App) -> None:
    g = _ready_game()

    async def closed(chat_id, *a, **k):
        from aiogram.exceptions import TelegramForbiddenError

        if chat_id > 0:
            raise TelegramForbiddenError(method=MagicMock(), message="blocked")
        return SimpleNamespace(message_id=5)

    app.bot.send_message = closed  # type: ignore[method-assign]
    app.bot.send_photo = closed  # type: ignore[method-assign]
    sent: list[str] = []

    async def group(game, text, **k):
        sent.append(text)

    app.safe_group = group  # type: ignore[method-assign]
    await app.start_game(g)
    assert g.phase == Phase.FINISHED
    assert sent and "dm_pending" not in sent[-1]
    assert t("uz", "start.dm_pending") in sent[-1]


@pytest.mark.asyncio
async def test_lobby_is_unpinned_on_start(app: App) -> None:
    g = _ready_game()
    g.lobby_message_id = 42
    await app.start_game(g)
    unpins = [c for c in app.bot.calls if c[0] == "unpin"]
    assert unpins and unpins[0][2]["message_id"] == 42


@pytest.mark.asyncio
async def test_retry_after_middleware_waits_then_succeeds(monkeypatch) -> None:
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    calls = {"n": 0}

    async def flaky(bot, method):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TelegramRetryAfter(method=MagicMock(), message="slow", retry_after=2)
        return "ok"

    assert await RetryAfterMiddleware()(flaky, MagicMock(), MagicMock()) == "ok"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_retry_after_middleware_gives_up_on_long_waits(monkeypatch) -> None:
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    async def slow(bot, method):
        raise TelegramRetryAfter(method=MagicMock(), message="slow", retry_after=600)

    with pytest.raises(TelegramRetryAfter):
        await RetryAfterMiddleware(max_wait=30)(slow, MagicMock(), MagicMock())


def test_instance_lock_is_exclusive(tmp_path) -> None:
    first = InstanceLock(tmp_path / "x.lock")
    second = InstanceLock(tmp_path / "x.lock")
    assert first.acquire()
    assert not second.acquire()
    first.release()
    assert second.acquire()
    second.release()


@pytest.mark.asyncio
async def test_alerter_cools_down_repeated_alerts() -> None:
    bot = SimpleNamespace(send_message=AsyncMock())
    alerts = Alerter(bot, owner_id=1, cooldown=3600)  # type: ignore[arg-type]
    assert await alerts.send("k", "first")
    assert not await alerts.send("k", "again")
    assert await alerts.send("other", "different key")
    alerts._last["k"] = -1e12  # cooldown over
    assert await alerts.send("k", "later")
    assert "(+1" in bot.send_message.await_args.args[1]
    assert not await Alerter(bot, owner_id=None).send("k", "no owner")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_avatar_uploads_only_when_file_changes(app: App) -> None:
    bot = SimpleNamespace(set_my_profile_photo=AsyncMock())
    await botmod._sync_profile_photo(bot)  # type: ignore[arg-type]
    await botmod._sync_profile_photo(bot)  # type: ignore[arg-type]
    assert bot.set_my_profile_photo.await_count == 1


@pytest.mark.asyncio
async def test_prune_and_daily_report(app: App) -> None:
    done = _ready_game()
    cancel(done)
    await app.persist(done)
    live = _ready_game()
    live.chat_id = -200
    await app.persist(live)
    report = await app.store.report_since(time.time() - 60)
    assert report["live"] == 1 and report["cancelled"] == 1 and report["games"] == 0
    assert await app.store.prune_finished(older_than_days=1) == 0  # too recent
    assert await app.store.prune_finished(older_than_days=-1) == 1
    assert await app.store.load(done.id) is None and await app.store.load(live.id)
    assert "O'yinlar" in await app.daily_report()


@pytest.mark.asyncio
async def test_error_handler_answers_callback_and_alerts(app: App) -> None:
    q = SimpleNamespace(from_user=SimpleNamespace(id=5), answer=AsyncMock())
    app.alerts = SimpleNamespace(send=AsyncMock())  # type: ignore[assignment]
    event = SimpleNamespace(exception=RuntimeError("boom"), update=SimpleNamespace(callback_query=q, message=None))
    assert await botmod.on_error(event) is True  # type: ignore[arg-type]
    q.answer.assert_awaited_once()
    assert q.answer.await_args.kwargs["show_alert"] is True
    app.alerts.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_recover_resends_role_dms_after_crash(app: App) -> None:
    from tezmafia.engine import start

    g = _ready_game()
    start(g)
    assert g.phase == Phase.ROLE_ASSIGNMENT
    await app.persist(g)
    await app.recover()
    dm_photos = [c for c in app.bot.calls if c[0] == "send_photo" and c[1][0] > 0]
    assert len(dm_photos) == len(g.players)
    assert (await app.store.load(g.id)).phase == Phase.NIGHT


def test_mark_dm_ok_helper_still_exported() -> None:
    assert callable(mark_dm_ok)
