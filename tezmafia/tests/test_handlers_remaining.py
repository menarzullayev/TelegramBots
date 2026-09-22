"""Remaining handler / timer / recover / run branches for full state coverage."""
from __future__ import annotations

import asyncio
import random
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import CommandObject
from aiogram.types import Chat, User

from tezmafia import bot as botmod
from tezmafia.bot import App
from tezmafia.config import Settings
from tezmafia.db import Store
from tezmafia.engine import (
    Phase,
    Winner,
    begin_night,
    begin_voting,
    join,
    mark_dm_ok,
    new_game,
    set_night_action,
    start as eng_start,
)


def _settings() -> Settings:
    return Settings(bot_token="1:TEST", bot_username="qorashahar_mafia_bot", owner_id=1)


class FakeBot:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self._n = 0

    def _msg(self) -> SimpleNamespace:
        self._n += 1
        return SimpleNamespace(message_id=self._n)

    async def send_message(self, *a, **k):
        self.calls.append(("send_message", a, k))
        return self._msg()

    async def send_photo(self, *a, **k):
        self.calls.append(("send_photo", a, k))
        return self._msg()

    async def send_rich_message(self, *a, **k):
        self.calls.append(("rich", a, k))
        return self._msg()

    async def edit_message_text(self, *a, **k):
        self.calls.append(("edit", a, k))
        return self._msg()

    async def pin_chat_message(self, *a, **k):
        self.calls.append(("pin", a, k))

    async def set_message_reaction(self, *a, **k):
        self.calls.append(("react", a, k))

    async def restrict_chat_member(self, *a, **k):
        raise TelegramBadRequest(method=MagicMock(), message="no")

    async def get_chat_member(self, *a, **k):
        raise TelegramBadRequest(method=MagicMock(), message="no")

    async def me(self):
        return SimpleNamespace(id=9)


class FakeMsg:
    def __init__(self, user: User | None, chat: Chat, text: str, bot: object) -> None:
        self.from_user = user
        self.chat = chat
        self.text = text
        self.bot = bot
        self.message_id = 1
        self.answers: list[tuple] = []

    async def answer(self, *a, **k):
        self.answers.append((a, k))
        return SimpleNamespace(message_id=1)

    async def edit_text(self, *a, **k):
        self.answers.append((a, k))
        return SimpleNamespace(message_id=1)

    async def delete(self) -> None:
        return None


@pytest.fixture
async def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    store = Store(f"sqlite+aiosqlite:///{tmp_path}/data/t.db")
    await store.init()
    bot = FakeBot()
    application = App(_settings(), store, bot)  # type: ignore[arg-type]
    botmod.app = application
    return application


def _ready(n: int = 5) -> object:
    g = new_game(-80, 100)
    for i in range(n):
        join(g, 100 + i, f"P{i}", f"p{i}")
        mark_dm_ok(g, 100 + i)
    return g


def _user(uid: int = 100) -> User:
    return User(id=uid, is_bot=False, first_name=f"U{uid}", username=f"u{uid}")


@pytest.mark.asyncio
async def test_timer_cancel_and_exception(app: App) -> None:
    async def boom() -> None:
        raise RuntimeError("timer-boom")

    app.schedule("boom", 0.01, boom)
    await asyncio.sleep(0.7)
    app.schedule("long", 10, boom)
    app.cancel_timer("long")
    await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_refresh_vote_empty_and_recover_future(app: App) -> None:
    g = _ready()
    g.vote_message_id = None
    await app.refresh_vote(g)
    eng_start(g, rng=random.Random(1))
    begin_night(g, 0, 1)
    g.deadline = 10**12
    await app.persist(g)
    await app.recover()
    g.phase = Phase.DAY
    g.deadline = 10**12
    await app.persist(g)
    await app.recover()
    g.phase = Phase.DAY
    begin_voting(g, 0, 1)
    g.deadline = 10**12
    await app.persist(g)
    await app.recover()


@pytest.mark.asyncio
async def test_timed_guards_detective_and_wins(app: App, monkeypatch) -> None:
    await app._timed_resolve_night("missing")
    await app._timed_begin_vote("missing")
    await app._timed_resolve_vote("missing")

    g = _ready()
    g.phase = Phase.DAY
    await app.persist(g)
    await app._timed_resolve_night(g.id)
    g.phase = Phase.NIGHT
    await app.persist(g)
    await app._timed_begin_vote(g.id)
    g.phase = Phase.DAY
    await app.persist(g)
    await app._timed_resolve_vote(g.id)

    g = _ready()
    for p, role in zip(g.players, ["mafia", "detective", "citizen", "citizen", "citizen"], strict=True):
        p.role = role
        p.faction = "mafia" if role == "mafia" else "town"
    begin_night(g, 0, 10)
    set_night_action(g, 101, 1)
    await app.persist(g)
    await app._timed_resolve_night(g.id)

    g = _ready()
    for p, role in zip(g.players, ["journalist", "doctor", "citizen", "citizen", "mafia"], strict=True):
        p.role = role
        p.faction = "mafia" if role in {"journalist", "mafia"} else "town"
    begin_night(g, 0, 10)
    set_night_action(g, 100, 2)
    set_night_action(g, 101, 3)
    await app.persist(g)
    await app._timed_resolve_night(g.id)

    g = _ready()
    for p, role in zip(g.players, ["mafia", "detective", "citizen", "citizen", "citizen"], strict=True):
        p.role = role
        p.faction = "mafia" if role == "mafia" else "town"
    for p in g.players[1:4]:
        p.alive = False
    begin_night(g, 0, 10)
    set_night_action(g, 100, 5)
    await app.persist(g)
    await app._timed_resolve_night(g.id)
    g = await app.store.load(g.id)
    assert g and g.phase == Phase.FINISHED

    g = _ready()
    for p, role in zip(g.players, ["mafia", "detective", "citizen", "citizen", "citizen"], strict=True):
        p.role = role
        p.faction = "mafia" if role == "mafia" else "town"
    g.phase = Phase.DAY
    begin_voting(g, 0, 10)
    from tezmafia.engine import set_vote

    for uid in (101, 102, 103, 104):
        set_vote(g, uid, 1)
    await app.persist(g)
    await app._timed_resolve_vote(g.id)
    g = await app.store.load(g.id)
    assert g and g.phase == Phase.LYNCH
    from tezmafia.engine import set_lynch_vote

    for uid in (101, 102, 103, 104):
        set_lynch_vote(g, uid, True)
    await app.persist(g)
    await app._timed_resolve_lynch(g.id)
    g = await app.store.load(g.id)
    assert g and g.winner == Winner.TOWN

    g = _ready()
    g.phase = Phase.FINISHED
    g.winner = Winner.MAFIA
    monkeypatch.setattr(botmod, "unmute_all", AsyncMock(side_effect=RuntimeError("unmute")))
    app.safe_photo = AsyncMock(return_value=None)  # type: ignore[method-assign]
    await app.finish(g)
    app.safe_photo = AsyncMock(side_effect=RuntimeError("photo-boom"))  # type: ignore[method-assign]
    await app.finish(g)


@pytest.mark.asyncio
async def test_recover_expired_gets_grace(app: App) -> None:
    from tezmafia.bot import RECOVER_GRACE
    from tezmafia.engine import Phase, begin_night, start

    g = _ready()
    start(g)
    begin_night(g, 0, 1)
    g.deadline = 0
    await app.persist(g)
    before = time.time()
    await app.recover()
    live = await app.store.load(g.id)
    assert live and live.phase == Phase.NIGHT
    assert live.deadline and live.deadline >= before + RECOVER_GRACE - 1
    assert g.id in app.timers


@pytest.mark.asyncio
async def test_recover_expired_day_vote_and_lonely_edges(app: App) -> None:
    from tezmafia.bot import cb_night, cmd_start, cmd_startgame, cmd_status

    g = _ready()
    g.phase = Phase.DAY
    g.deadline = 0
    await app.persist(g)
    await app.recover()
    g = _ready()
    g.id = "vote-exp"
    g.phase = Phase.VOTING
    g.deadline = 0
    await app.persist(g)
    await app.recover()

    ghost = FakeMsg(_user(7777), Chat(id=7777, type=ChatType.PRIVATE), "/status", app.bot)
    await cmd_status(ghost)

    host = _user(100)
    chat = Chat(id=-80, type=ChatType.GROUP, title="T")
    await cmd_startgame(FakeMsg(host, chat, "/startgame", app.bot))
    msg = FakeMsg(host, chat, "/mafia", app.bot)
    from tezmafia.bot import cmd_mafia

    await cmd_mafia(msg)
    live = await app.store.active_in_chat(-80)
    assert live
    await cmd_startgame(FakeMsg(host, chat, "/startgame", app.bot))

    live.phase = Phase.NIGHT
    await app.persist(live)
    await cmd_start(
        FakeMsg(_user(8888), Chat(id=8888, type=ChatType.PRIVATE), f"/start g_{live.id}", app.bot),
        CommandObject(command="start", args=f"g_{live.id}"),
    )
    await cb_night(
        SimpleNamespace(
            from_user=_user(100),
            data="nm:does-not-exist:1",
            message=FakeMsg(host, Chat(id=100, type=ChatType.PRIVATE), "x", app.bot),
            answer=AsyncMock(),
        )
    )
    for gid in list(app.timers):
        app.cancel_timer(gid)


@pytest.mark.asyncio
async def test_private_status_start_reason_and_vote_ok(app: App) -> None:
    from tezmafia.bot import cb_role_card, cb_vote, cmd_leave, cmd_roles, cmd_startgame, cmd_status, cmd_vote
    from tezmafia.engine import set_vote

    chat = Chat(id=-4243, type=ChatType.GROUP, title="V")
    host = User(id=4242, is_bot=False, first_name="Host", username="host4242")
    g = new_game(-4243, 4242)
    join(g, 4242, "Host", "host4242")
    await app.persist(g)
    loaded = await app.store.active_in_chat(-4243)
    assert loaded and loaded.host_id == 4242 and len(loaded.players) == 1
    await cmd_status(FakeMsg(host, Chat(id=4242, type=ChatType.PRIVATE), "/status", app.bot))
    start_msg = FakeMsg(host, chat, "/startgame", app.bot)
    await cmd_startgame(start_msg)
    assert start_msg.answers, "startgame should refuse too_few"

    for i in range(1, 5):
        join(g, 4242 + i, f"P{i}", f"p{i}")
        mark_dm_ok(g, 4242 + i)
    mark_dm_ok(g, 4242)
    await app.persist(g)
    go = FakeMsg(host, chat, "/startgame", app.bot)
    await cmd_startgame(go)
    live = await app.store.active_in_chat(-4243)
    assert live and live.phase in {Phase.NIGHT, Phase.DAY, Phase.FINISHED}

    g = live
    g.phase = Phase.DAY
    begin_voting(g, 0, 30)
    await app.persist(g)
    voter = User(id=4243, is_bot=False, first_name="P1", username="p1")
    await cmd_vote(
        FakeMsg(voter, chat, "/vote 1", app.bot),
        CommandObject(command="vote", args="1"),
    )
    set_vote(g, 4243, None)
    await app.persist(g)
    await cb_vote(
        SimpleNamespace(
            from_user=voter,
            data=f"v:{g.id}:1",
            message=FakeMsg(voter, chat, "x", app.bot),
            answer=AsyncMock(),
        )
    )
    await cmd_roles(FakeMsg(host, chat, "/roles", app.bot))
    await cb_role_card(
        SimpleNamespace(
            from_user=host,
            data="hr:mafia",
            message=FakeMsg(host, chat, "x", app.bot),
            answer=AsyncMock(),
        )
    )
    g3 = new_game(-4244, 4242)
    join(g3, 4242, "Host", "host4242")
    await app.persist(g3)
    await cmd_leave(FakeMsg(host, Chat(id=-4244, type=ChatType.GROUP, title="L"), "/leave", app.bot))
    for gid in list(app.timers):
        app.cancel_timer(gid)



@pytest.mark.asyncio
async def test_all_command_and_callback_edges(app: App) -> None:
    from tezmafia.bot import (
        cb_leave,
        cb_night,
        cb_start,
        cb_vote,
        cb_vote_clear,
        cmd_action,
        cmd_cancel,
        cmd_help,
        cmd_join,
        cmd_mafia,
        cmd_start,
        cmd_startgame,
        cmd_status,
        cmd_vote,
    )

    host = _user(100)
    other = _user(999)
    chat = Chat(id=-80, type=ChatType.GROUP, title="T")
    priv = Chat(id=100, type=ChatType.PRIVATE)
    bot = app.bot
    msg = FakeMsg(host, chat, "/mafia", bot)
    await cmd_mafia(FakeMsg(None, chat, "/mafia", bot))
    await cmd_mafia(msg)
    await cmd_mafia(msg)  # existing lobby refresh
    g = await app.store.active_in_chat(-80)
    assert g

    await cmd_join(FakeMsg(None, chat, "/join", bot))
    await cmd_join(FakeMsg(host, Chat(id=100, type=ChatType.PRIVATE), "/join", bot))
    empty = FakeMsg(host, Chat(id=-81, type=ChatType.GROUP, title="E"), "/join", bot)
    await cmd_join(empty)

    g.max_players = 1
    await app.persist(g)
    await cmd_join(FakeMsg(_user(101), chat, "/join", bot))

    await cmd_cancel(FakeMsg(None, chat, "/cancel", bot))
    await cmd_cancel(FakeMsg(host, Chat(id=100, type=ChatType.PRIVATE), "/cancel", bot))
    await cmd_cancel(FakeMsg(other, chat, "/cancel", bot))
    await cmd_cancel(FakeMsg(host, Chat(id=-81, type=ChatType.GROUP, title="E"), "/cancel", bot))
    await cmd_cancel(FakeMsg(host, chat, "/cancel", bot))

    await cmd_status(FakeMsg(host, Chat(id=-81, type=ChatType.GROUP, title="E"), "/status", bot))
    await cmd_status(FakeMsg(host, priv, "/status", bot))
    await cmd_mafia(msg)
    g = await app.store.active_in_chat(-80)
    assert g
    await cmd_status(FakeMsg(host, chat, "/status", bot))
    g.phase = Phase.DAY
    await app.persist(g)
    await cmd_status(FakeMsg(host, chat, "/status", bot))
    await cmd_mafia(msg)  # existing not-lobby
    g.phase = Phase.LOBBY
    await app.persist(g)

    rich_fail = FakeMsg(host, chat, "/help", bot)
    rich_fail.bot = SimpleNamespace(
        send_rich_message=AsyncMock(side_effect=TelegramAPIError(method=MagicMock(), message="no"))
    )
    await cmd_help(rich_fail)

    await cmd_startgame(FakeMsg(None, chat, "/startgame", bot))
    await cmd_startgame(FakeMsg(host, priv, "/startgame", bot))
    await cmd_startgame(FakeMsg(host, Chat(id=-81, type=ChatType.GROUP, title="E"), "/startgame", bot))
    await cmd_startgame(FakeMsg(other, chat, "/startgame", bot))
    await cmd_startgame(FakeMsg(host, chat, "/startgame", bot))  # too_few

    await cmd_action(FakeMsg(host, chat, "/action 1", bot), CommandObject(command="action", args="1"))
    await cmd_action(FakeMsg(host, priv, "/action x", bot), CommandObject(command="action", args="x"))
    await cmd_action(FakeMsg(host, priv, "/action 1", bot), CommandObject(command="action", args="1"))

    await cmd_vote(FakeMsg(None, chat, "/vote 1", bot), CommandObject(command="vote", args="1"))
    await cmd_vote(FakeMsg(host, chat, "/vote x", bot), CommandObject(command="vote", args="x"))
    await cmd_vote(FakeMsg(host, Chat(id=-81, type=ChatType.GROUP, title="E"), "/vote 1", bot), CommandObject(command="vote", args="1"))
    await cmd_vote(FakeMsg(host, chat, "/vote 1", bot), CommandObject(command="vote", args="1"))
    await cmd_vote(FakeMsg(host, priv, "/vote 1", bot), CommandObject(command="vote", args="1"))

    await cmd_start(FakeMsg(None, priv, "/start", bot), CommandObject(command="start", args=""))
    await cmd_start(FakeMsg(host, chat, "/start", bot), CommandObject(command="start", args=""))
    await cmd_start(FakeMsg(host, priv, "/start", bot), CommandObject(command="start", args=""))
    await cmd_start(FakeMsg(other, priv, f"/start g_{g.id}", bot), CommandObject(command="start", args=f"g_{g.id}"))

    q = SimpleNamespace(from_user=None, data=None, message=msg, answer=AsyncMock())
    await cb_start(q)
    await cb_leave(q)
    await cb_night(q)
    await cb_vote(q)
    await cb_vote_clear(q)
    q = SimpleNamespace(from_user=other, data=f"s:{g.id}", message=msg, answer=AsyncMock())
    await cb_start(q)
    q = SimpleNamespace(from_user=host, data=f"s:{g.id}", message=msg, answer=AsyncMock())
    await cb_start(q)  # too_few
    await cb_leave(SimpleNamespace(from_user=host, data=f"l:{g.id}", message=msg, answer=AsyncMock()))
    await cb_night(
        SimpleNamespace(
            from_user=host,
            data=f"nm:{g.id}:1",
            message=FakeMsg(host, chat, "x", bot),
            answer=AsyncMock(),
        )
    )
    await cb_night(
        SimpleNamespace(
            from_user=host,
            data=f"nm:{g.id}:1",
            message=FakeMsg(host, priv, "x", bot),
            answer=AsyncMock(),
        )
    )
    await cb_vote(SimpleNamespace(from_user=host, data=f"v:{g.id}:1", message=msg, answer=AsyncMock()))
    await cb_vote_clear(SimpleNamespace(from_user=host, data=f"vx:{g.id}", message=msg, answer=AsyncMock()))


@pytest.mark.asyncio
async def test_setup_profile_branches(app: App, tmp_path, monkeypatch) -> None:
    from tezmafia.bot import setup_bot_profile

    bot = FakeBot()
    bot.set_my_name = AsyncMock(side_effect=RuntimeError("flood"))
    bot.set_my_short_description = AsyncMock()
    bot.set_my_description = AsyncMock()
    bot.set_my_commands = AsyncMock()
    bot.set_my_default_administrator_rights = AsyncMock()
    bot.set_my_profile_photo = AsyncMock(side_effect=RuntimeError("pic"))
    monkeypatch.chdir(tmp_path)
    await setup_bot_profile(bot)  # type: ignore[arg-type]
    langs = [c.kwargs.get("language_code") for c in bot.set_my_commands.await_args_list]
    assert None in langs and "en" in langs and "uk" in langs
    marker = tmp_path / "data" / ".profile_ok"
    marker.parent.mkdir(exist_ok=True)
    marker.write_text("ok\n")
    bot.set_my_name = AsyncMock()
    await setup_bot_profile(bot)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_run_recovers_and_polls(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    monkeypatch.setenv("BOT_TOKEN", "1:TEST")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/data/run.db")

    class DummyBot:
        def __init__(self, *a, **k):
            pass

        async def get_webhook_info(self):
            return SimpleNamespace(url="")

    class DummyDP:
        def include_router(self, _r):
            return None

        def resolve_used_update_types(self):
            return []

        async def start_polling(self, *a, **k):
            return None

    monkeypatch.setattr(botmod, "Bot", DummyBot)
    monkeypatch.setattr(botmod, "Dispatcher", DummyDP)
    monkeypatch.setattr(botmod, "setup_bot_profile", AsyncMock(side_effect=RuntimeError("skip")))
    monkeypatch.setattr(botmod, "DefaultBotProperties", lambda **k: None)
    await botmod.run()


@pytest.mark.asyncio
async def test_assert_polling_contract_ok_and_rejects_webhook() -> None:
    from tezmafia.bot import assert_polling_contract

    ok = SimpleNamespace(get_webhook_info=AsyncMock(return_value=SimpleNamespace(url="")))
    await assert_polling_contract(ok)  # type: ignore[arg-type]

    bad = SimpleNamespace(
        get_webhook_info=AsyncMock(
            return_value=SimpleNamespace(url="https://serverless.example/secret-path")
        )
    )
    with pytest.raises(RuntimeError, match=r"webhook attached \(serverless.example\)"):
        await assert_polling_contract(bad)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_parity_commands_and_lynch(app: App) -> None:
    from tezmafia.bot import (
        cb_lang,
        cb_lynch,
        cmd_extend,
        cmd_next,
        cmd_profile,
        cmd_chats,
        cmd_settings,
        cmd_shop,
        cmd_buy,
        cmd_top,
        cb_buy,
        cb_menu,
        night_delete,
    )
    from tezmafia.engine import Phase, begin_night, begin_voting, set_vote

    host = User(id=4242, is_bot=False, first_name="Host", username="host4242")
    chat = Chat(id=-5001, type=ChatType.GROUP, title="P")
    g = new_game(-5001, 4242)
    join(g, 4242, "Host", "host4242")
    await app.persist(g)
    await cmd_extend(FakeMsg(host, chat, "/extend", app.bot))
    await cmd_extend(FakeMsg(host, Chat(id=1, type=ChatType.PRIVATE), "/extend", app.bot))
    await cmd_top(FakeMsg(host, chat, "/top", app.bot))
    await cmd_profile(FakeMsg(host, chat, "/profile", app.bot))
    await cmd_shop(FakeMsg(host, chat, "/shop", app.bot))
    await cmd_buy(FakeMsg(host, chat, "/buy", app.bot), CommandObject(command="buy", args=""))
    await cmd_buy(FakeMsg(host, chat, "/buy yoq", app.bot), CommandObject(command="buy", args="yoq"))
    await cmd_buy(FakeMsg(host, chat, "/buy role yoq", app.bot), CommandObject(command="buy", args="role yoq"))
    await app.store.credit_wallet(4242, "Host", coins=60)
    await cmd_buy(FakeMsg(host, chat, "/buy maska", app.bot), CommandObject(command="buy", args="maska"))
    await cmd_buy(FakeMsg(host, chat, "/buy role komissar", app.bot), CommandObject(command="buy", args="role komissar"))
    await cb_menu(
        SimpleNamespace(
            from_user=host,
            data="m:profile",
            message=FakeMsg(host, chat, "x", app.bot),
            answer=AsyncMock(),
        )
    )
    await cb_menu(
        SimpleNamespace(
            from_user=host,
            data="m:shop",
            message=FakeMsg(host, chat, "x", app.bot),
            answer=AsyncMock(),
        )
    )
    await cb_menu(
        SimpleNamespace(
            from_user=host,
            data="m:roles",
            message=FakeMsg(host, chat, "x", app.bot),
            answer=AsyncMock(),
        )
    )
    await cb_menu(
        SimpleNamespace(
            from_user=host,
            data="m:lang",
            message=FakeMsg(host, chat, "x", app.bot),
            answer=AsyncMock(),
        )
    )
    await cb_menu(SimpleNamespace(from_user=host, data="m:shop", message=None, answer=AsyncMock()))
    await cb_buy(
        SimpleNamespace(
            from_user=host,
            data="buy:shield",
            message=FakeMsg(host, chat, "x", app.bot),
            answer=AsyncMock(),
        )
    )
    await app.store.credit_wallet(4242, "Host", coins=40)
    await cb_buy(
        SimpleNamespace(
            from_user=host,
            data="buy:shield",
            message=FakeMsg(host, chat, "x", app.bot),
            answer=AsyncMock(),
        )
    )
    await cb_menu(
        SimpleNamespace(
            from_user=host,
            data="m:chats",
            message=FakeMsg(host, chat, "x", app.bot),
            answer=AsyncMock(),
        )
    )
    await cmd_chats(FakeMsg(host, chat, "/chats", app.bot))
    await cmd_settings(FakeMsg(host, chat, "/settings", app.bot))
    await cb_lang(SimpleNamespace(data="lang:ru", message=FakeMsg(host, chat, "x", app.bot), answer=AsyncMock()))
    await cmd_next(FakeMsg(host, chat, "/next", app.bot))
    await cmd_next(FakeMsg(User(id=9, is_bot=False, first_name="X"), chat, "/next", app.bot))

    for i in range(1, 5):
        join(g, 4242 + i, f"P{i}", f"p{i}")
        mark_dm_ok(g, 4242 + i)
    mark_dm_ok(g, 4242)
    g.phase = Phase.DAY
    begin_voting(g, 0, 10)
    for uid in (4243, 4244, 4245, 4246):
        set_vote(g, uid, 1)
    await app.persist(g)
    await app._timed_resolve_vote(g.id)
    live = await app.store.load(g.id)
    assert live and live.phase == Phase.LYNCH
    await cb_lynch(
        SimpleNamespace(
            from_user=User(id=4243, is_bot=False, first_name="P1"),
            data=f"ly:{live.id}:1",
            message=FakeMsg(host, chat, "x", app.bot),
            answer=AsyncMock(),
        )
    )
    await cb_lynch(SimpleNamespace(from_user=host, data="ly:missing:1", message=FakeMsg(host, chat, "x", app.bot), answer=AsyncMock()))
    await app._timed_resolve_lynch(live.id)
    await app._timed_resolve_lynch("missing")
    await app._timed_lobby_expire("missing")

    g2 = new_game(-5002, 4242)
    join(g2, 4242, "Host", "host4242")
    await app.persist(g2)
    await app._timed_lobby_expire(g2.id)

    g3 = new_game(-5003, 4242)
    for i in range(5):
        join(g3, 4242 + i, f"P{i}", f"p{i}")
        mark_dm_ok(g3, 4242 + i)
    g3.phase = Phase.NIGHT
    await app.persist(g3)
    await night_delete(FakeMsg(host, Chat(id=-5003, type=ChatType.GROUP, title="N"), "gap", app.bot))
    await night_delete(FakeMsg(host, Chat(id=-5003, type=ChatType.GROUP, title="N"), "/status", app.bot))
    await cmd_next(FakeMsg(host, Chat(id=-5003, type=ChatType.GROUP, title="N"), "/next", app.bot))

    await app.store.bump_stat(1, "A", True)
    await app.store.bump_stat(1, "A", False)
    assert (await app.store.get_stat(1))[1] == 2
    assert await app.store.top_stats()
    assert await app.store.get_lang(-5001) == "ru"
    await app.store.set_lang(-9, "xx")

    g4 = _ready()
    begin_night(g4, 0, 1)
    await app.persist(g4)
    await app.skip_phase(g4)
    g4.phase = Phase.DAY
    await app.persist(g4)
    await app.skip_phase(g4)
    await app.record_stats(g4)
    g4.winner = "maniac"
    g4.players[0].role = "maniac"
    await app.record_stats(g4)
    g4.winner = "suicide"
    g4.players[0].role = "suicide"
    await app.record_stats(g4)
