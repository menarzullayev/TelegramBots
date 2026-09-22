from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Chat, User

from tezmafia.bot import App
from tezmafia.bot import router
from tezmafia.config import Settings
from tezmafia.db import Store
from tezmafia.engine import Phase, Winner, begin_night, join, mark_dm_ok, new_game
from tezmafia import bot as botmod


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

    async def delete_message(self, *a, **k):
        self.calls.append(("delete", a, k))


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


def _ready_game(n: int = 5) -> object:
    g = new_game(-100, 100)
    for i in range(n):
        join(g, 100 + i, f"P{i}", f"p{i}")
        mark_dm_ok(g, 100 + i)
    return g


@pytest.mark.asyncio
async def test_app_lobby_start_finish(app: App) -> None:
    g = _ready_game()
    await app.persist(g)
    await app.refresh_lobby(g)
    assert g.lobby_message_id
    await app.refresh_lobby(g)
    await app.start_game(g)
    assert g.phase == Phase.NIGHT
    await app._timed_resolve_night(g.id)
    g = await app.store.load(g.id)
    assert g.phase in {Phase.DAY, Phase.FINISHED}
    if g.phase == Phase.DAY:
        await app._timed_begin_vote(g.id)
        g = await app.store.load(g.id)
        assert g.phase == Phase.VOTING
        g.winner = Winner.TOWN
        g.phase = Phase.FINISHED
        await app.finish(g)
    await app.react(1, 1, "👍")
    assert await app.dm(1, "hi")
    app.bot.send_message = AsyncMock(side_effect=TelegramForbiddenError(method=MagicMock(), message="x"))  # type: ignore[method-assign]
    assert await app.dm(1, "hi") is False


@pytest.mark.asyncio
async def test_role_ticket_and_killer_loadout(app: App) -> None:
    g = _ready_game()
    await app.store.credit_wallet(100, "P0", coins=70)
    assert (await app.store.buy_next_role(100, "P0", "detective"))[0]
    await app.store.credit_wallet(101, "P1", coins=30)
    assert (await app.store.buy_item(101, "P1", "killer_shield"))[0]
    await app.start_game(g)
    host = next(p for p in g.players if p.user_id == 100)
    assert host.role == "detective"
    p1 = next(p for p in g.players if p.user_id == 101)
    assert p1.shop_killer_shield is True
    await app.store.credit_wallet(102, "P2", coins=35)
    g2 = _ready_game()
    g2.id = "ticket2"
    assert (await app.store.buy_next_role(102, "P2", "journalist"))[0]
    await app.start_game(g2)
    assert (await app.store.get_account(102))["coins"] == 35


@pytest.mark.asyncio
async def test_role_ticket_first_wins_refunds_second(app: App) -> None:
    g = _ready_game()
    await app.store.credit_wallet(100, "P0", coins=35)
    await app.store.credit_wallet(101, "P1", coins=35)
    assert (await app.store.buy_next_role(100, "P0", "detective"))[0]
    assert (await app.store.buy_next_role(101, "P1", "detective"))[0]
    await app.start_game(g)
    host = next(p for p in g.players if p.user_id == 100)
    other = next(p for p in g.players if p.user_id == 101)
    assert host.role == "detective"
    assert other.role != "detective"
    assert (await app.store.get_account(100))["next_role"] == ""
    assert (await app.store.get_account(101))["coins"] == 35
    assert (await app.store.get_account(101))["next_role"] == ""


@pytest.mark.asyncio
async def test_role_ticket_survives_dm_cancel(app: App) -> None:
    g = _ready_game()
    await app.store.credit_wallet(100, "P0", coins=35)
    await app.store.credit_wallet(101, "P1", coins=35)
    assert (await app.store.buy_next_role(100, "P0", "detective"))[0]
    assert (await app.store.buy_next_role(101, "P1", "detective"))[0]

    async def dm_fail(chat_id, *a, **k):
        if chat_id > 0:
            raise TelegramForbiddenError(method=MagicMock(), message="x")
        return SimpleNamespace(message_id=99)

    app.bot.send_message = dm_fail  # type: ignore[method-assign]
    await app.start_game(g)
    assert g.phase == Phase.FINISHED
    acc0 = await app.store.get_account(100)
    acc1 = await app.store.get_account(101)
    assert acc0["next_role"] == "detective"
    assert acc1["next_role"] == "detective"
    assert acc0["coins"] == 0
    assert acc1["coins"] == 0


@pytest.mark.asyncio
async def test_recover_and_cancel_timer(app: App) -> None:
    g = _ready_game()
    begin_night(g, 0, 1)
    await app.persist(g)
    await app.recover()
    g2 = _ready_game()
    g2.id = "roleass"
    g2.phase = Phase.ROLE_ASSIGNMENT
    await app.persist(g2)
    await app.recover()

    async def boom() -> None:
        raise RuntimeError("x")

    app.schedule("t", 0.01, boom)
    await asyncio.sleep(0.05)
    app.schedule("t2", 10, boom)
    app.cancel_timer("t2")
    app.cancel_timer("missing")

    async def self_cancel() -> None:
        app.timers["self"] = asyncio.current_task()  # type: ignore[assignment]
        app.cancel_timer("self")

    t = asyncio.create_task(self_cancel())
    await t


class FakeMsg:
    def __init__(self, user: User, chat: Chat, text: str, bot: object) -> None:
        self.from_user = user
        self.chat = chat
        self.text = text
        self.bot = bot
        self.message_id = 1

    async def answer(self, *a, **k):
        return SimpleNamespace(message_id=1)


@pytest.mark.asyncio
async def test_handlers(app: App) -> None:
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

    user = User(id=100, is_bot=False, first_name="Host", username="host")
    chat = Chat(id=-50, type=ChatType.GROUP, title="T")
    msg = FakeMsg(user, chat, "/mafia", app.bot)
    await cmd_mafia(msg)
    await cmd_join(msg)
    await cmd_status(msg)
    await cmd_help(msg)
    await cmd_cancel(msg)
    await cmd_startgame(msg)
    priv = FakeMsg(user, Chat(id=100, type=ChatType.PRIVATE), "/start g_none", app.bot)
    # CommandObject passed separately
    from aiogram.filters import CommandObject

    await cmd_start(priv, CommandObject(command="start", args="g_missing"))
    await cmd_status(priv)
    await cmd_action(priv, CommandObject(command="action", args="1"))
    await cmd_vote(msg, CommandObject(command="vote", args="1"))
    q = SimpleNamespace(
        from_user=user,
        data="s:missing",
        message=msg,
        answer=AsyncMock(),
    )
    await cb_start(q)
    q.data = "l:missing"
    await cb_leave(q)
    q.data = "nm:x:1"
    await cb_night(q)
    q.data = "v:x:1"
    await cb_vote(q)
    q.data = "vx:x"
    await cb_vote_clear(q)
    assert router.name == "tezmafia"


@pytest.mark.asyncio
async def test_app_edges(app: App) -> None:
    from tezmafia.engine import begin_voting, start as eng_start
    import random

    g = _ready_game()
    await app.persist(g)
    g.vote_message_id = 7
    await app.refresh_vote(g)
    app.bot.edit_message_text = AsyncMock(side_effect=TelegramBadRequest(method=MagicMock(), message="e"))  # type: ignore[method-assign]
    await app.refresh_vote(g)
    g.lobby_message_id = 3
    await app.refresh_lobby(g)
    app.bot.pin_chat_message = AsyncMock(side_effect=TelegramBadRequest(method=MagicMock(), message="p"))  # type: ignore[method-assign]
    g.lobby_message_id = None
    await app.refresh_lobby(g)

    async def dm_fail(chat_id, *a, **k):
        if chat_id > 0:
            raise TelegramForbiddenError(method=MagicMock(), message="x")
        return SimpleNamespace(message_id=99)

    app.bot.send_message = dm_fail  # type: ignore[method-assign]
    g = _ready_game()
    await app.start_game(g)
    assert g.phase == Phase.FINISHED

    app.bot.send_message = FakeBot.send_message.__get__(app.bot, FakeBot)  # type: ignore[method-assign]
    g = _ready_game()
    app.settings.first_phase = "day"  # type: ignore[misc]
    await app.persist(g)
    await app.start_game(g)
    assert g.phase == Phase.DAY

    g = _ready_game()
    eng_start(g, rng=random.Random(1))
    begin_night(g, 0, 1)
    g.deadline = 0
    await app.persist(g)
    await app.recover()
    g = _ready_game()
    eng_start(g, rng=random.Random(2))
    g.phase = Phase.DAY
    begin_voting(g, 0, 1)
    g.deadline = 0
    await app.persist(g)
    await app._timed_resolve_vote(g.id)

    app.bot.set_message_reaction = AsyncMock(side_effect=TelegramBadRequest(method=MagicMock(), message="r"))  # type: ignore[method-assign]
    await app.react(1, 1, "👍")
    await app.safe_photo(1, "missing.png", "c")
    app.bot.send_photo = AsyncMock(side_effect=TelegramBadRequest(method=MagicMock(), message="ph"))  # type: ignore[method-assign]
    await app.safe_photo(1, "town-win.png", "c")
    app.bot.send_message = AsyncMock(side_effect=TelegramBadRequest(method=MagicMock(), message="g"))  # type: ignore[method-assign]
    await app.safe_group(g, "x")


def test_main(monkeypatch) -> None:
    from tezmafia import __main__ as mm

    monkeypatch.setattr(mm.asyncio, "run", lambda _c: None)
    mm.main()


@pytest.mark.asyncio
async def test_setup_and_live_handlers(app: App) -> None:
    from tezmafia.bot import (
        cb_leave,
        cb_night,
        cb_start,
        cb_vote,
        cb_vote_clear,
        cmd_action,
        cmd_join,
        cmd_mafia,
        cmd_start,
        cmd_startgame,
        cmd_vote,
        setup_bot_profile,
    )
    from aiogram.filters import CommandObject

    bot = app.bot
    bot.set_my_name = AsyncMock()
    bot.set_my_short_description = AsyncMock()
    bot.set_my_description = AsyncMock()
    bot.set_my_commands = AsyncMock()
    bot.set_my_default_administrator_rights = AsyncMock()
    bot.set_my_profile_photo = AsyncMock()
    await setup_bot_profile(bot)  # type: ignore[arg-type]

    host = User(id=200, is_bot=False, first_name="H", username="h")
    chat = Chat(id=-77, type=ChatType.GROUP, title="G")
    msg = FakeMsg(host, chat, "/mafia", bot)
    await cmd_mafia(msg)
    game = await app.store.active_in_chat(-77)
    assert game
    for i in range(1, 5):
        u = User(id=200 + i, is_bot=False, first_name=f"P{i}", username=f"p{i}")
        await cmd_join(FakeMsg(u, chat, "/join", bot))
        await cmd_start(
            FakeMsg(u, Chat(id=200 + i, type=ChatType.PRIVATE), f"/start g_{game.id}", bot),
            CommandObject(command="start", args=f"g_{game.id}"),
        )
    await cmd_start(
        FakeMsg(host, Chat(id=200, type=ChatType.PRIVATE), f"/start g_{game.id}", bot),
        CommandObject(command="start", args=f"g_{game.id}"),
    )
    q = SimpleNamespace(from_user=host, data=f"s:{game.id}", message=msg, answer=AsyncMock())
    await cb_start(q)
    game = await app.store.load(game.id)
    assert game and game.phase == Phase.NIGHT
    mafia = next(p for p in game.players if p.role == "mafia")
    town = next(p for p in game.players if p.faction == "town")
    priv = FakeMsg(
        User(id=mafia.user_id, is_bot=False, first_name="M", username="m"),
        Chat(id=mafia.user_id, type=ChatType.PRIVATE),
        f"/action {town.seat}",
        bot,
    )
    await cmd_action(priv, CommandObject(command="action", args=str(town.seat)))
    nq = SimpleNamespace(
        from_user=User(id=mafia.user_id, is_bot=False, first_name="M", username="m"),
        data=f"nm:{game.id}:{town.seat}",
        message=priv,
        answer=AsyncMock(),
    )
    await cb_night(nq)
    await app._timed_resolve_night(game.id)
    game = await app.store.load(game.id)
    if game.phase == Phase.DAY:
        await app._timed_begin_vote(game.id)
        game = await app.store.load(game.id)
        voter = next(p for p in game.alive_players() if p.seat != 1)
        await cmd_vote(
            FakeMsg(
                User(id=voter.user_id, is_bot=False, first_name="V", username="v"),
                chat,
                "/vote 1",
                bot,
            ),
            CommandObject(command="vote", args="1"),
        )
        vq = SimpleNamespace(
            from_user=User(id=voter.user_id, is_bot=False, first_name="V", username="v"),
            data=f"v:{game.id}:1",
            message=msg,
            answer=AsyncMock(),
        )
        await cb_vote(vq)
        await cb_vote_clear(SimpleNamespace(from_user=vq.from_user, data=f"vx:{game.id}", message=msg, answer=AsyncMock()))
        await app._timed_resolve_vote(game.id)
    # leftover lobby leave
    g2 = await app.store.active_in_chat(-77)
    if g2 and g2.phase == Phase.LOBBY:
        await cb_leave(SimpleNamespace(from_user=host, data=f"l:{g2.id}", message=msg, answer=AsyncMock()))
    await cmd_startgame(msg)
    await cmd_mafia(FakeMsg(host, Chat(id=200, type=ChatType.PRIVATE), "/mafia", bot))
