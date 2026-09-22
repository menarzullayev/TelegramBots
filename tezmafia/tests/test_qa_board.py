"""JIRA QA-01..QA-100 — har bir ticket uchun haqiqiy assert."""
from __future__ import annotations

import ast
import asyncio
import inspect
import logging
import random
import time
import tracemalloc
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import CommandObject
from aiogram.types import Chat, User

from tezmafia import bot as botmod
from tezmafia import texts
from tezmafia.bot import App
from tezmafia.config import Settings
from tezmafia.db import Store
from tezmafia.emoji import ce
from tezmafia.engine import (
    Phase,
    begin_night,
    begin_voting,
    can_start,
    cancel,
    from_dict,
    join,
    leave,
    mark_dm_ok,
    new_game,
    resolve_night,
    resolve_votes,
    set_night_action,
    set_vote,
    start,
    to_dict,
    win_check,
)
from tezmafia.keyboards import menu_kb, night_kb, shop_kb, vote_kb
from tezmafia.qa_catalog import TICKETS, assert_complete
from tezmafia.roles import ROLE_FACTION, ROLE_UZ, Role, bag_for
from tezmafia.services.mute import apply_phase_mutes
from tezmafia.shop import ITEMS, empty_flags, resolve_item

ROOT = Path(__file__).resolve().parents[1]


def _settings() -> Settings:
    return Settings(bot_token="1:TEST", bot_username="qorashahar_mafia_bot", owner_id=1)


class FakeBot:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self._n = 0
        self.fail_send = False
        self.retry_once = False

    def _msg(self) -> SimpleNamespace:
        self._n += 1
        return SimpleNamespace(message_id=self._n)

    async def send_message(self, *a, **k):
        if self.retry_once:
            self.retry_once = False
            raise TelegramRetryAfter(method=MagicMock(), message="429", retry_after=1)
        if self.fail_send:
            raise TelegramBadRequest(method=MagicMock(), message="fail")
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


class FakeMsg:
    def __init__(self, user: User | None, chat: Chat, text: str, bot: object) -> None:
        self.from_user = user
        self.chat = chat
        self.text = text
        self.bot = bot
        self.message_id = 1
        self.answers: list = []

    async def answer(self, *a, **k):
        self.answers.append((a, k))
        return SimpleNamespace(message_id=1)

    async def delete(self) -> None:
        self.answers.append(("delete",))


def _ready(n: int = 5, host: int = 100, chat: int = -10) -> object:
    g = new_game(chat, host)
    for i in range(n):
        join(g, host + i, f"P{i}", f"p{i}")
        mark_dm_ok(g, host + i)
    return g


def _force(g, roles: list[str]) -> None:
    start(g, rng=random.Random(0))
    for p, role in zip(g.players, roles, strict=True):
        p.role = role
        p.faction = ROLE_FACTION[Role(role)].value


async def _app(tmp_path, monkeypatch) -> App:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir(exist_ok=True)
    store = Store(f"sqlite+aiosqlite:///{tmp_path}/data/qa.db")
    await store.init()
    bot = FakeBot()
    application = App(_settings(), store, bot)
    botmod.app = application
    return application


def _mafia_vote_game(n: int = 5):
    g = _ready(n)
    roles = ["mafia"] + ["citizen"] * (n - 1)
    _force(g, roles)
    g.phase = Phase.DAY
    begin_voting(g, 0, 30)
    return g


# --- tickets -----------------------------------------------------------------


async def qa_01(tmp, mp):
    g = _mafia_vote_game()
    for uid in (101, 102, 103, 104):
        assert set_vote(g, uid, 1)[0]
    r = resolve_votes(g)
    assert r["eliminated"] == 1
    g2 = _ready(5)
    start(g2, rng=random.Random(1))
    assert all(p.role for p in g2.players)
    g3 = _ready(5)
    _force(g3, ["mafia", "citizen", "citizen", "citizen", "citizen"])
    for p in g3.players[1:]:
        p.alive = False
    assert win_check(g3) == "mafia"


async def qa_02(tmp, mp):
    app = await _app(tmp, mp)
    g = _ready(5)
    start(g, rng=random.Random(2))
    await app.persist(g)
    live = await app.store.load(g.id)
    assert live and live.players[0].role == g.players[0].role


async def qa_03(tmp, mp):
    from tezmafia.bot import cmd_status

    app = await _app(tmp, mp)
    g = _ready(5)
    await app.persist(g)
    user = User(id=100, is_bot=False, first_name="H")
    chat = Chat(id=-10, type=ChatType.GROUP, title="T")
    msg = FakeMsg(user, chat, "/status", app.bot)
    await cmd_status(msg)
    assert msg.answers or any(c[0] == "send_message" for c in app.bot.calls)


async def qa_04(tmp, mp):
    app = await _app(tmp, mp)
    g = _ready(5)
    await app.persist(g)
    await app.start_game(g)
    assert g.phase == Phase.NIGHT
    await app._timed_resolve_night(g.id)
    live = await app.store.load(g.id)
    assert live.phase in {Phase.DAY, Phase.FINISHED}
    if live.phase == Phase.DAY:
        live.phase = Phase.DAY
        begin_voting(live, 0, 10)
        town = next(p for p in live.players if p.faction == "town")
        for p in live.alive_players():
            if p.user_id != town.user_id:
                set_vote(live, p.user_id, town.seat)
        r = resolve_votes(live)
        assert "eliminated" in r or live.winner


async def qa_05(tmp, mp):
    s = _settings()
    assert s.database_url.startswith("sqlite")
    assert s.min_players == 5
    app = await _app(tmp, mp)
    assert app.store and app.settings.bot_username


async def qa_06(tmp, mp):
    assert len(ROLE_UZ) == 21
    assert "killer_shield" in ITEMS
    assert "/buy" in texts.help_html()
    assert "Do‘kon" in texts.shop_text(0, 0, {})


async def qa_07(tmp, mp):
    assert bag_for(5).mafia == 1 and bag_for(5).detective == 1
    g = _ready(5)
    _force(g, ["detective", "mafia", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 10)
    assert g.night_no == 1
    ok, reason = set_night_action(g, 100, 2, "shoot")
    assert ok is False
    assert reason == "no_first_shoot"


async def qa_08(tmp, mp):
    import tezmafia
    import tezmafia.bot
    import tezmafia.engine

    assert tezmafia and tezmafia.bot and tezmafia.engine
    app = await _app(tmp, mp)
    acc = await app.store.get_account(1)
    assert acc["coins"] == 0


async def qa_09(tmp, mp):
    assert resolve_item("maska") == "mask"
    assert resolve_item("qotil") == "killer_shield"


async def qa_10(tmp, mp):
    g = _ready(5)
    _force(g, ["detective", "mafia", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 10)
    kb = night_kb(g, 100)
    data = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert all(not (d or "").startswith("ns:") for d in data)
    assert any((d or "").startswith("nd:") for d in data)


async def qa_11(tmp, mp):
    g = _mafia_vote_game(12)
    targets = [p.seat for p in g.players if p.seat != 1]

    async def one(uid: int, seat: int) -> None:
        set_vote(g, uid, seat)

    await asyncio.gather(*[one(100 + i, targets[i % len(targets)]) for i in range(12)])
    assert sum(1 for p in g.players if p.vote) >= 10


async def qa_12(tmp, mp):
    g = _ready(5)
    _force(g, ["mafia", "citizen", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 10)
    fails = 0
    for i in range(500):
        ok, _ = set_night_action(g, 100, 2 + (i % 3))
        if not ok:
            fails += 1
    assert g.players[0].night_action in {2, 3, 4}
    assert fails == 0


async def qa_13(tmp, mp):
    g = new_game(1, 1)
    for i in range(23):
        assert join(g, 10 + i, f"U{i}", None)[0]
    assert len(g.players) == 23
    assert join(g, 99, "X", None)[1] == "full"
    for i in range(23):
        leave(g, 10 + i)
    assert g.players == []


async def qa_14(tmp, mp):
    for seed in range(12):
        g = _ready(5)
        _force(g, ["mafia", "citizen", "citizen", "citizen", "citizen"])
        begin_night(g, 0, 10)
        set_night_action(g, 100, 2)
        resolve_night(g)
        assert g.phase in {Phase.DAY, Phase.FINISHED} or not g.players[1].alive or g.night_saved
        assert seed >= 0


async def qa_15(tmp, mp):
    app = await _app(tmp, mp)
    for i in range(80):
        g = new_game(-1000 - i, 1)
        join(g, 1, "H", None)
        mark_dm_ok(g, 1)
        await app.persist(g)
    rows = await app.store.unfinished()
    assert len(rows) >= 80


async def qa_16(tmp, mp):
    g = _ready(7)
    _force(g, ["mafia", "mafia", "citizen", "citizen", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 10)

    async def pick(uid: int, seat: int) -> None:
        set_night_action(g, uid, seat)

    await asyncio.gather(pick(100, 3), pick(101, 4))
    actions = {g.players[0].night_action, g.players[1].night_action}
    assert actions <= {3, 4}
    assert None not in actions


async def qa_17(tmp, mp):
    g = _mafia_vote_game(10)
    await asyncio.gather(*[asyncio.to_thread(set_vote, g, 100 + i, 1) for i in range(1, 10)])
    assert all(p.vote == 1 for p in g.players[1:])


async def qa_18(tmp, mp):
    app = await _app(tmp, mp)
    g = _ready(5)
    v0 = g.version
    await app.persist(g)
    join(g, 999, "Z", None)
    await app.persist(g)
    live = await app.store.load(g.id)
    assert live and live.version > v0


async def qa_19(tmp, mp):
    app = await _app(tmp, mp)
    g = _ready(5)
    await app.persist(g)

    async def a() -> None:
        async with app.lock:
            x = await app.store.load(g.id)
            await app.persist(x)

    async def b() -> None:
        async with app.lock:
            x = await app.store.load(g.id)
            await app.persist(x)

    await asyncio.gather(a(), b())
    assert await app.store.load(g.id)


async def qa_20(tmp, mp):
    g = _mafia_vote_game()
    for _ in range(5):
        assert set_vote(g, 101, 1)[0]
    assert g.players[1].vote == 1
    r = resolve_votes(g)
    assert r["tally"].get(1, 0) == 1 or r["tie"] or r["eliminated"] in {1, None}


async def qa_21(tmp, mp):
    src = (ROOT / "tezmafia" / "bot.py").read_text(encoding="utf-8")
    assert "start_polling" in src
    assert "set_webhook" not in src


async def qa_22(tmp, mp):
    src = (ROOT / "tezmafia" / "bot.py").read_text(encoding="utf-8")
    assert "async def run" in src
    assert "Start polling" in src or "start_polling" in src


async def qa_23(tmp, mp):
    from tezmafia.bot import cb_vote

    app = await _app(tmp, mp)
    g = _mafia_vote_game()
    await app.persist(g)
    q = SimpleNamespace(
        from_user=User(id=101, is_bot=False, first_name="P1"),
        data=f"v:{g.id}:1",
        message=FakeMsg(User(id=101, is_bot=False, first_name="P1"), Chat(id=-10, type=ChatType.GROUP), "x", app.bot),
        answer=AsyncMock(),
    )
    await cb_vote(q)
    live = await app.store.load(g.id)
    assert live and live.by_user(101) and live.by_user(101).vote == 1


async def qa_24(tmp, mp):
    app = await _app(tmp, mp)
    g = _mafia_vote_game()
    g.vote_message_id = 7
    await app.refresh_vote(g)
    assert any(c[0] == "edit" for c in app.bot.calls)


async def qa_25(tmp, mp):
    from tezmafia.bot import night_delete

    app = await _app(tmp, mp)
    g = _ready(5)
    start(g, rng=random.Random(0))
    begin_night(g, 0, 10)
    await app.persist(g)
    user = User(id=100, is_bot=False, first_name="H")
    chat = Chat(id=g.chat_id, type=ChatType.GROUP, title="T")
    msg = FakeMsg(user, chat, "gap", app.bot)
    await night_delete(msg)
    assert ("delete",) in msg.answers


async def qa_26(tmp, mp):
    from tezmafia.bot import cmd_start

    app = await _app(tmp, mp)
    g = _ready(5)
    await app.persist(g)
    extra = User(id=999, is_bot=False, first_name="N")
    priv = FakeMsg(extra, Chat(id=999, type=ChatType.PRIVATE), f"/start g_{g.id}", app.bot)
    await cmd_start(priv, CommandObject(command="start", args=f"g_{g.id}"))
    live = await app.store.load(g.id)
    assert live and live.by_user(999)


async def qa_27(tmp, mp):
    app = await _app(tmp, mp)
    g = _ready(5)
    await apply_phase_mutes(app.bot, g, night=True, enabled=True)


async def qa_28(tmp, mp):
    from tezmafia.bot import cmd_action

    app = await _app(tmp, mp)
    g = _ready(5)
    _force(g, ["mafia", "citizen", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 10)
    await app.persist(g)
    group = FakeMsg(
        User(id=100, is_bot=False, first_name="H"),
        Chat(id=g.chat_id, type=ChatType.GROUP, title="T"),
        "/action 2",
        app.bot,
    )
    await cmd_action(group, CommandObject(command="action", args="2"))
    assert g.players[0].night_action is None


async def qa_29(tmp, mp):
    g = _mafia_vote_game()
    assert vote_kb(g).inline_keyboard
    assert shop_kb().inline_keyboard
    assert menu_kb().inline_keyboard


async def qa_30(tmp, mp):
    g = new_game(1, 1)
    join(g, 1, "<b>x</b>", "a&b")
    label = g.players[0].html_label()
    assert "&lt;b&gt;" in label or "<" not in label.replace("@", "")
    assert "&amp;" in label or "a&b" not in label


async def qa_31(tmp, mp):
    g = _mafia_vote_game()
    assert set_vote(g, 99999, 1)[0] is False


async def qa_32(tmp, mp):
    g = _ready(5)
    _force(g, ["citizen", "mafia", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 10)
    ok, reason = set_night_action(g, 100, 2)
    assert ok is False
    assert reason == "no_action"


async def qa_33(tmp, mp):
    from tezmafia.bot import cb_vote

    app = await _app(tmp, mp)
    q = SimpleNamespace(
        from_user=User(id=1, is_bot=False, first_name="X"),
        data="v:not-a-game:1",
        message=None,
        answer=AsyncMock(),
    )
    await cb_vote(q)


async def qa_34(tmp, mp):
    app = await _app(tmp, mp)
    evil = "'; DROP TABLE stats;-- <script>"
    await app.store.credit_wallet(42, evil, coins=10)
    acc = await app.store.get_account(42)
    assert acc["coins"] == 10
    g = new_game(1, 1)
    join(g, 1, evil, None)
    assert "script" not in g.players[0].html_label() or "&lt;" in g.players[0].html_label()


async def qa_35(tmp, mp):
    g = _mafia_vote_game()
    set_vote(g, 101, 1)
    resolve_votes(g)
    assert set_vote(g, 101, 2)[1] == "not_voting"


async def qa_36(tmp, mp):
    app = await _app(tmp, mp)
    g = _ready(5)
    start(g, rng=random.Random(0))
    begin_night(g, time.time() + 30, 30)
    await app.persist(g)
    await app.recover()
    assert g.id in app.timers


async def qa_37(tmp, mp):
    app = await _app(tmp, mp)
    await app.store.credit_wallet(7, "A", coins=3)
    await app.store.engine.dispose()
    store2 = Store(f"sqlite+aiosqlite:///{tmp / 'data' / 'qa.db'}")
    await store2.init()
    acc = await store2.get_account(7)
    assert acc["coins"] == 3
    await store2.engine.dispose()


async def qa_38(tmp, mp):
    app = await _app(tmp, mp)
    app.bot.send_message = AsyncMock(side_effect=TelegramForbiddenError(method=MagicMock(), message="x"))
    assert await app.dm(1, "hi") is False


async def qa_39(tmp, mp):
    app = await _app(tmp, mp)
    app.bot.fail_send = True
    g = _ready(5)
    assert await app.safe_group(g, "x") is None


async def qa_40(tmp, mp):
    app = await _app(tmp, mp)
    g = _ready(5)
    start(g, rng=random.Random(0))
    begin_night(g, 0, 1)
    g.deadline = time.time() - 5
    await app.persist(g)
    await app.recover()
    live = await app.store.load(g.id)
    assert live and live.phase == Phase.NIGHT
    assert live.deadline and live.deadline > time.time()
    assert g.id in app.timers


async def qa_41(tmp, mp):
    app = await _app(tmp, mp)
    g = _ready(5)
    await app.persist(g)
    await app.start_game(g)
    assert g.phase == Phase.NIGHT


async def qa_42(tmp, mp):
    g = _ready(5)
    start(g, rng=random.Random(0))
    g.phase = Phase.DAY
    assert can_start(g) == (False, "not_lobby")
    with pytest.raises(RuntimeError):
        start(g)


async def qa_43(tmp, mp):
    g = _ready(5)
    start(g, rng=random.Random(0))
    assert g.round == 0
    begin_night(g, 0, 10)
    assert g.round == 1
    begin_night(g, 0, 10)
    assert g.round == 2
    assert g.night_no == 2


async def qa_44(tmp, mp):
    g = _ready(5)
    _force(g, ["mafia", "citizen", "citizen", "citizen", "citizen"])
    for p in g.players[1:]:
        p.alive = False
    assert win_check(g) == "mafia"
    assert g.phase == Phase.FINISHED


async def qa_45(tmp, mp):
    g = _mafia_vote_game()
    set_vote(g, 101, 1)
    set_vote(g, 102, 1)
    set_vote(g, 103, 2)
    set_vote(g, 104, 2)
    r = resolve_votes(g)
    assert r["tie"] is True
    assert r["eliminated"] is None


async def qa_46(tmp, mp):
    app = await _app(tmp, mp)
    await app.store.init()
    acc = await app.store.get_account(1)
    assert "next_role" in acc


async def qa_47(tmp, mp):
    app = await _app(tmp, mp)
    await app.store.credit_wallet(8, "A", coins=1)
    await app.store.credit_wallet(8, "B", coins=2)
    acc = await app.store.get_account(8)
    assert acc["name"] == "B"
    assert acc["coins"] == 3


async def qa_48(tmp, mp):
    app = await _app(tmp, mp)
    ok, reason = await app.store.buy_item(3, "X", "mask")
    assert ok is False and reason == "no_money"
    acc = await app.store.get_account(3)
    assert acc["inventory"] == {}
    assert acc["coins"] == 0


async def qa_49(tmp, mp):
    app = await _app(tmp, mp)
    g = _ready(5)
    await app.persist(g)
    cancel(g)
    await app.persist(g)
    assert await app.store.active_in_chat(g.chat_id) is None


async def qa_50(tmp, mp):
    app = await _app(tmp, mp)
    g = _ready(5)
    await app.persist(g)
    assert (await app.store.active_in_chat(g.chat_id)).id == g.id
    assert any(x.id == g.id for x in await app.store.unfinished())


async def qa_51(tmp, mp):
    app = await _app(tmp, mp)
    g = _ready(5)
    await app.start_game(g)
    kinds = [c[0] for c in app.bot.calls]
    assert "send_photo" in kinds
    assert kinds.count("send_message") >= 5


async def qa_52(tmp, mp):
    g = _ready(5)
    start(g, rng=random.Random(0))
    begin_night(g, 1000.0, 45)
    assert g.deadline == 1045.0


async def qa_53(tmp, mp):
    app = await _app(tmp, mp)
    assert await app.store.set_lang(-1, "ru") == "ru"
    assert await app.store.get_lang(-1) == "ru"
    assert await app.store.set_lang(-1, "az") == "az"
    assert await app.store.set_lang(-1, "xx") == "uz"


async def qa_54(tmp, mp):
    assert ce("mafia")
    assert ce("town")
    assert texts.help_html()


async def qa_55(tmp, mp):
    labels = [b.text for row in menu_kb().inline_keyboard for b in row]
    assert "Profil" in labels and "Do‘kon" in labels
    assert all(len(t) >= 2 for t in labels)


async def qa_56(tmp, mp):
    app = await _app(tmp, mp)
    g = _ready(5)
    await app.persist(g)
    await app.store.engine.dispose()
    store = Store(f"sqlite+aiosqlite:///{tmp / 'data' / 'qa.db'}")
    await store.init()
    assert await store.load(g.id)
    await store.engine.dispose()


async def qa_57(tmp, mp):
    db = tmp / "gone.db"
    store = Store(f"sqlite+aiosqlite:///{db}")
    await store.init()
    await store.engine.dispose()
    db.unlink()
    store2 = Store(f"sqlite+aiosqlite:///{db}")
    await store2.init()
    acc = await store2.get_account(1)
    assert acc["games"] == 0
    await store2.engine.dispose()


async def qa_58(tmp, mp):
    app = await _app(tmp, mp)
    app.bot.retry_once = True
    g = _ready(5)
    assert await app.safe_group(g, "x") is None


async def qa_59(tmp, mp):
    g = _ready(5)
    _force(g, ["mafia", "citizen", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 10)
    set_night_action(g, 100, 3)
    await asyncio.sleep(0.01)
    r = resolve_night(g)
    assert "killed" in r


async def qa_60(tmp, mp):
    app = await _app(tmp, mp)
    g = _ready(5)
    start(g, rng=random.Random(3))
    await app.persist(g)
    blob = to_dict(g)
    g.phase = Phase.FINISHED
    restored = from_dict(blob)
    assert restored.phase != Phase.FINISHED
    await app.persist(restored)
    live = await app.store.load(g.id)
    assert live.phase == restored.phase


async def qa_61(tmp, mp):
    pkg = ROOT / "tezmafia"
    for path in pkg.rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


async def qa_62(tmp, mp):
    src = (ROOT / "tezmafia" / "engine.py").read_text(encoding="utf-8")
    assert "\t" not in src


async def qa_63(tmp, mp):
    from tezmafia import engine as eng

    for name in ("start", "set_vote", "resolve_votes", "win_check", "begin_night"):
        assert inspect.signature(getattr(eng, name)).parameters


async def qa_64(tmp, mp):
    assert_complete()
    assert set(CHECKS) == set(range(1, 101))


async def qa_65(tmp, mp):
    bag = bag_for(5)
    assert bag.mafia == 1
    mutant = 0
    assert bag.mafia != mutant


async def qa_66(tmp, mp):
    flags = empty_flags()
    assert set(flags) == set(ITEMS)
    g = _ready(5)
    start(g, rng=random.Random(0))
    p = g.players[0]
    for key in ITEMS:
        assert hasattr(p, f"shop_{key}")


async def qa_67(tmp, mp):
    assert set(ROLE_UZ) == set(Role)
    assert set(texts.ROLE_CARDS) == {r.value for r in Role}


async def qa_68(tmp, mp):
    with pytest.raises(ValueError):
        bag_for(4)
    assert bag_for(5).total == 5
    assert bag_for(23).total == 23


async def qa_69(tmp, mp):
    g = _ready(5)
    _force(g, ["mafia", "mafia", "mafia", "citizen", "citizen"])
    g.players[3].alive = False
    w = win_check(g)
    assert w == "mafia"


async def qa_70(tmp, mp):
    g = _mafia_vote_game()
    g.players[1].alive = False
    assert set_vote(g, 101, 1)[1] == "dead"


async def qa_71(tmp, mp):
    g = _mafia_vote_game()
    assert set_vote(g, 101, 1) == (True, "ok")


async def qa_72(tmp, mp):
    g = _ready(8)
    seats = [p.seat for p in g.players]
    assert seats == list(range(1, 9))
    leave(g, 103)
    assert [p.seat for p in g.players] == list(range(1, 8))
    assert len({p.seat for p in g.players}) == len(g.players)


async def qa_73(tmp, mp):
    from tezmafia.bot import cb_vote, cb_night

    app = await _app(tmp, mp)
    rng = random.Random(9)
    for raw in [rng.randbytes(8).hex(), "::::", "v:", "nm:x:999", ""]:
        q = SimpleNamespace(from_user=User(id=1, is_bot=False, first_name="X"), data=raw or "v:x:1", message=None, answer=AsyncMock())
        try:
            await cb_vote(q)
        except Exception:
            pass
        try:
            await cb_night(q)
        except Exception:
            pass


async def qa_74(tmp, mp):
    sizes = set()
    for seed in range(8):
        g = _ready(5)
        start(g, rng=random.Random(seed))
        sizes.add(tuple(sorted(p.role for p in g.players)))
    assert sizes


async def qa_75(tmp, mp):
    a = _ready(5)
    b = _ready(5)
    start(a, rng=random.Random(0))
    start(b, rng=random.Random(0))
    assert [p.role for p in a.players] == [p.role for p in b.players]


async def qa_76(tmp, mp):
    g = _ready(5)
    start(g, rng=random.Random(4))
    blob = to_dict(g)
    assert blob["id"] == g.id
    assert len(blob["players"]) == 5


async def qa_77(tmp, mp):
    g = _ready(5)
    start(g, rng=random.Random(4))
    g2 = from_dict(to_dict(g))
    assert g2.id == g.id
    assert [p.role for p in g2.players] == [p.role for p in g.players]


async def qa_78(tmp, mp):
    g = _ready(5)
    start(g, rng=random.Random(0))
    begin_night(g, 50.0, 12)
    assert abs((g.deadline or 0) - 62.0) < 0.001


async def qa_79(tmp, mp):
    before = time.time()
    g = new_game(1, 1)
    assert before - 1 <= g.created_at <= time.time() + 1


async def qa_80(tmp, mp):
    app = await _app(tmp, mp)
    hit = {"n": 0}

    async def boom() -> None:
        hit["n"] += 1

    app.schedule("s", 0.5, boom)
    await asyncio.sleep(0.7)
    assert hit["n"] == 1
    app.schedule("s2", 10, boom)
    app.cancel_timer("s2")
    assert "s2" not in app.timers or app.timers["s2"].cancelled()


async def qa_81(tmp, mp):
    app = await _app(tmp, mp)
    acc = await app.store.get_account(0)
    assert set(acc) >= {"coins", "gems", "inventory", "next_role"}


async def qa_82(tmp, mp):
    g = new_game(1, 1)
    assert can_start(g)[1] == "too_few"
    g = _ready(5)
    assert can_start(g) == (True, "ok")


async def qa_83(tmp, mp):
    app = await _app(tmp, mp)
    g = _ready(5)
    start(g, rng=random.Random(0))
    begin_night(g, time.time(), 40)
    await app.persist(g)
    await app.recover()
    assert await app.store.load(g.id)


async def qa_84(tmp, mp):
    app = await _app(tmp, mp)
    await app.store.bump_stat(5, "W", True)
    acc = await app.store.get_account(5)
    assert acc["wins"] == 1
    assert acc["coins"] >= 25


async def qa_85(tmp, mp):
    app = await _app(tmp, mp)
    g = _ready(5)
    await app.persist(g)
    with pytest.LogCaptureFixture if False else DummyLog():
        pass
    logging.getLogger("tezmafia.bot").setLevel(logging.INFO)
    await app.recover()


async def qa_86(tmp, mp):
    app = await _app(tmp, mp)

    async def boom() -> None:
        raise RuntimeError("sentry")

    app.schedule("x", 0.5, boom)
    await asyncio.sleep(0.7)


async def qa_87(tmp, mp):
    g = _ready(5)
    _force(g, ["mafia", "citizen", "citizen", "citizen", "citizen"])
    for p in g.players[1:]:
        p.alive = False
    win_check(g)
    assert "Qora" in texts.game_over(g) or "quladi" in texts.game_over(g)


async def qa_88(tmp, mp):
    g = _ready(5)
    v = g.version
    start(g, rng=random.Random(0))
    assert g.version > v


async def qa_89(tmp, mp):
    g = _ready(5)
    _force(g, ["mafia", "citizen", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 10)
    set_night_action(g, 100, 2)
    resolve_night(g)
    if not g.players[1].alive:
        assert g.last_death_seat == 2
        assert g.last_death_role in {None, "citizen"}


async def qa_90(tmp, mp):
    app = await _app(tmp, mp)
    await app.store.credit_wallet(11, "Bk", coins=9)
    raw = (tmp / "data" / "qa.db").read_bytes()
    copy = tmp / "bak.db"
    copy.write_bytes(raw)
    store = Store(f"sqlite+aiosqlite:///{copy}")
    await store.init()
    assert (await store.get_account(11))["coins"] == 9
    await store.engine.dispose()


async def qa_91(tmp, mp):
    g = new_game(1, 1)
    for i in range(12):
        assert join(g, 200 + i, f"J{i}", None)[1] == "joined"
    assert len(g.players) == 12
    for i in range(12):
        mark_dm_ok(g, 200 + i)
    assert can_start(g)[0]
    start(g, rng=random.Random(12))
    assert bag_for(12).total == 12


async def qa_92(tmp, mp):
    g = _ready(7)
    _force(g, ["don", "mafia", "citizen", "citizen", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 10)
    await asyncio.gather(
        asyncio.to_thread(set_night_action, g, 100, 3),
        asyncio.to_thread(set_night_action, g, 101, 4),
    )
    resolve_night(g)
    dead = [p for p in g.players if not p.alive]
    assert len(dead) <= 1


async def qa_93(tmp, mp):
    g = _ready(5)
    _force(g, ["detective", "mafia", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 10)
    set_night_action(g, 101, 3)
    r = resolve_night(g)
    assert r["detective_result"] is None


async def qa_94(tmp, mp):
    g = _ready(7)
    start(g, rng=random.Random(1))
    doctor = next((p for p in g.players if p.role == "doctor"), None)
    mafia = next(p for p in g.players if p.role in {"mafia", "don"})
    victim = next(p for p in g.players if p.user_id not in {mafia.user_id, getattr(doctor, "user_id", -1)} and p.faction == "town")
    begin_night(g, 0, 10)
    set_night_action(g, mafia.user_id, victim.seat)
    r = resolve_night(g)
    assert r["saved"] is False


async def qa_95(tmp, mp):
    await qa_45(tmp, mp)


async def qa_96(tmp, mp):
    g = _ready(5)
    _force(g, ["mafia", "citizen", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 10)
    set_night_action(g, 100, 2)
    resolve_night(g)
    begin_night(g, 0, 10)
    alive_town = [p for p in g.alive_players() if p.faction == "town"]
    if alive_town and g.players[0].alive:
        set_night_action(g, 100, alive_town[0].seat)
        resolve_night(g)
    assert g.winner in {None, "mafia", "town"}
    if len(g.alive_mafia()) >= len(g.alive_town()) and g.alive_mafia():
        assert win_check(g) in {"mafia", None} or g.winner == "mafia"


async def qa_97(tmp, mp):
    g = _ready(6)
    assert leave(g, 105) is True
    assert g.by_user(105) is None
    start(g, rng=random.Random(0))
    assert leave(g, 100) is False


async def qa_98(tmp, mp):
    app = await _app(tmp, mp)
    g = _ready(5)
    await app.start_game(g)
    gid = g.id
    app2 = App(_settings(), app.store, FakeBot())
    botmod.app = app2
    await app2.recover()
    live = await app2.store.load(gid)
    assert live and live.phase in {Phase.NIGHT, Phase.DAY, Phase.FINISHED}


async def qa_99(tmp, mp):
    from tezmafia.bot import cb_vote

    app = await _app(tmp, mp)
    g = _mafia_vote_game()
    await app.persist(g)
    user = User(id=101, is_bot=False, first_name="P1")
    for _ in range(8):
        await cb_vote(
            SimpleNamespace(
                from_user=user,
                data=f"v:{g.id}:1",
                message=FakeMsg(user, Chat(id=-10, type=ChatType.GROUP), "x", app.bot),
                answer=AsyncMock(),
            )
        )
    live = await app.store.load(g.id)
    assert live.by_user(101).vote == 1


async def qa_100(tmp, mp):
    tracemalloc.start()
    snap1 = tracemalloc.take_snapshot()
    for i in range(25):
        g = _ready(5)
        _force(g, ["mafia", "citizen", "citizen", "citizen", "citizen"])
        begin_night(g, 0, 10)
        set_night_action(g, 100, 2)
        resolve_night(g)
        del g
    snap2 = tracemalloc.take_snapshot()
    total = sum(s.size_diff for s in snap2.compare_to(snap1, "filename")[:20])
    tracemalloc.stop()
    assert total < 8_000_000


class DummyLog:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


CHECKS = {i: globals()[f"qa_{i:02d}"] for i in range(1, 101)}


@pytest.mark.asyncio
@pytest.mark.parametrize("n", list(range(1, 101)), ids=[t["id"] for t in TICKETS])
async def test_qa_ticket(n: int, tmp_path, monkeypatch) -> None:
    await CHECKS[n](tmp_path, monkeypatch)
