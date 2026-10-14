"""G1: custom role set, anonymous vote, room of the dead, rematch."""

from __future__ import annotations

import random
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.enums import ChatType
from aiogram.types import Chat

from tests.test_bot_e2e import FakeBot, _ready_game, _settings
from tezmafia import bot as botmod
from tezmafia import texts
from tezmafia.bot import App
from tezmafia.db import Store
from tezmafia.engine import Phase, begin_night, begin_voting, cancel, set_vote, start
from tezmafia.i18n import t
from tezmafia.roles import SPECIALS, bag_for, chaos_bag, without


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


@pytest.mark.parametrize("n", [8, 12, 23])
def test_switched_off_roles_become_citizens(n: int) -> None:
    bag = without(bag_for(n), {"maniac", "sergeant", "mafia"})  # core roles cannot be switched off
    assert bag.total == n and bag.maniac == 0 and bag.sergeant == 0
    assert bag.mafia == bag_for(n).mafia


def test_chaos_never_draws_a_switched_off_role() -> None:
    off = set(SPECIALS) - {"mayor"}
    for seed in range(10):
        bag = chaos_bag(12, random.Random(seed), off)
        assert all(getattr(bag, k) == 0 for k in off)
        assert bag.total == 12


def test_start_respects_the_groups_role_set() -> None:
    g = _ready_game(12)
    g.disabled_roles = ["maniac", "lawyer", "mayor"]
    start(g, random.Random(1))
    assert not {"maniac", "lawyer", "mayor"} & {p.role for p in g.players}
    assert "role.citizen" not in texts.roles_public(g)  # counts come from the dealt roles, translated


def test_anonymous_tally_hides_the_split() -> None:
    g = _ready_game(6)
    start(g)
    g.phase = Phase.DAY
    begin_voting(g, 0, 30)
    alive = g.alive_players()
    set_vote(g, alive[0].user_id, alive[1].seat)
    open_text = texts.vote_tally(g)
    assert alive[1].html_label() in open_text
    g.anon_vote = True
    secret = texts.vote_tally(g)
    assert alive[1].html_label() not in secret
    assert t("uz", "vote.anon", n=1, m=len(alive)) in secret


@pytest.mark.asyncio
async def test_group_settings_flow_into_the_game(app: App) -> None:
    await app.store.set_chat_setting(-5, "anon", True)
    await app.store.set_chat_setting(-5, "off", ["maniac", "bogus"])
    cfg = await app.game_cfg(-5)
    assert cfg["anon_vote"] is True and cfg["disabled_roles"] == ["maniac"]


def _cfg_query(data: str, user_id: int = 100) -> SimpleNamespace:
    return SimpleNamespace(
        data=data,
        from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(chat=Chat(id=-77, type=ChatType.SUPERGROUP), edit_text=AsyncMock(), edit_reply_markup=AsyncMock()),
        answer=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_role_toggles_are_admin_only(app: App) -> None:
    q = _cfg_query("cfr:maniac")
    await botmod.cb_config_role(q)  # type: ignore[arg-type]
    assert q.answer.await_args.args[0] == t("uz", "config.admin_only")
    assert (await app.chat_cfg(-77))["off"] == []


@pytest.mark.asyncio
async def test_admin_switches_roles_off_and_on(app: App) -> None:
    app.bot.get_chat_member = AsyncMock(return_value=SimpleNamespace(status="creator"))  # type: ignore[method-assign]
    await botmod.cb_config_role(_cfg_query("cfr:maniac"))  # type: ignore[arg-type]
    await botmod.cb_config_role(_cfg_query("cfr:mage"))  # type: ignore[arg-type]
    assert (await app.chat_cfg(-77))["off"] == ["maniac", "mage"]
    await botmod.cb_config_role(_cfg_query("cfr:maniac"))  # type: ignore[arg-type]
    assert (await app.chat_cfg(-77))["off"] == ["mage"]
    bad = _cfg_query("cfr:mafia")  # core role: not toggleable
    await botmod.cb_config_role(bad)  # type: ignore[arg-type]
    assert (await app.chat_cfg(-77))["off"] == ["mage"]
    await botmod.cb_config(_cfg_query("cfg:anon"))  # type: ignore[arg-type]
    assert (await app.chat_cfg(-77))["anon"] is True
    roles_screen = _cfg_query("cfg:roles")
    await botmod.cb_config(roles_screen)  # type: ignore[arg-type]
    assert roles_screen.message.edit_text.await_args.args[0] == t("uz", "config.roles_title")


def _dm(user_id: int, text: str) -> SimpleNamespace:
    return SimpleNamespace(from_user=SimpleNamespace(id=user_id), text=text, answer=AsyncMock())


@pytest.mark.asyncio
async def test_room_of_the_dead_reaches_only_the_dead(app: App) -> None:
    g = _ready_game(6)
    start(g)
    begin_night(g, time.time(), 45)
    g.players[0].alive = False
    g.players[1].alive = False
    await app.persist(g)
    sent: list[tuple[int, str]] = []
    app.dm = AsyncMock(side_effect=lambda uid, text, **k: sent.append((uid, text)) or True)  # type: ignore[method-assign]
    await botmod.on_last_words(_dm(g.players[0].user_id, "it was <the> don"))  # type: ignore[arg-type]
    assert [uid for uid, _ in sent] == [g.players[1].user_id]
    assert "&lt;the&gt;" in sent[0][1]
    sent.clear()
    await botmod.on_last_words(_dm(g.players[2].user_id, "I am alive"))  # type: ignore[arg-type]
    assert sent == []  # the living cannot write into the room


@pytest.mark.asyncio
async def test_rematch_opens_a_lobby_and_invites_previous_players(app: App) -> None:
    old = _ready_game(5)
    cancel(old)
    await app.persist(old)
    invited: list[int] = []
    app.dm = AsyncMock(side_effect=lambda uid, text, **k: invited.append(uid) or True)  # type: ignore[method-assign]
    q = SimpleNamespace(
        data=f"rm:{old.id}",
        from_user=SimpleNamespace(id=100, first_name="Host", username=None),
        message=SimpleNamespace(chat=Chat(id=-100, type=ChatType.SUPERGROUP)),
        answer=AsyncMock(),
    )
    await botmod.cb_rematch(q)  # type: ignore[arg-type]
    lobby = await app.store.active_in_chat(-100)
    assert lobby and lobby.phase == Phase.LOBBY and lobby.host_id == 100
    assert sorted(invited) == sorted(p.user_id for p in old.players if p.user_id != 100)
    again = SimpleNamespace(**{**q.__dict__, "answer": AsyncMock()})
    await botmod.cb_rematch(again)  # type: ignore[arg-type]
    assert again.answer.await_args.kwargs.get("show_alert") is True  # table already open
