"""F5a: per-group /config and game modes (classic, chaos, secret, fast)."""

from __future__ import annotations

import random
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.enums import ChatType
from aiogram.types import Chat

from tests.test_bot_e2e import FakeBot, FakeMsg, _ready_game, _settings
from tezmafia import bot as botmod
from tezmafia import texts
from tezmafia.bot import App
from tezmafia.db import Store
from tezmafia.engine import begin_night, from_dict, start, to_dict
from tezmafia.i18n import t
from tezmafia.roles import ROLE_FACTION, Faction, Role, bag_for, chaos_bag


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


@pytest.mark.parametrize("n", range(5, 24))
def test_chaos_bag_keeps_the_table_size_and_core(n: int) -> None:
    classic = bag_for(n)
    for seed in range(5):
        bag = chaos_bag(n, random.Random(seed))
        assert bag.total == n
        assert (bag.mafia, bag.don, bag.detective, bag.doctor) == (
            classic.mafia, classic.don, classic.detective, classic.doctor
        )
        if n < 10:
            assert bag.lawyer == bag.journalist == bag.killer == 0


def test_chaos_really_varies() -> None:
    draws = {tuple(r.value for r in chaos_bag(12, random.Random(seed)).as_list()) for seed in range(20)}
    assert len(draws) > 5


def test_old_saved_games_load_as_classic() -> None:
    g = _ready_game()
    data = to_dict(g)
    data.pop("mode")
    data.pop("timers")
    loaded = from_dict(data)
    assert loaded.mode == "classic" and loaded.timers == {}


def test_chaos_start_and_public_counts() -> None:
    g = _ready_game(8)
    g.mode = "chaos"
    start(g, random.Random(3))
    dealt = [p.role for p in g.players]
    text = texts.roles_public(g)
    for role in set(dealt):
        assert f"{t('uz', f'role.{role}')}: {dealt.count(role)}" in text
    mafia = sum(1 for r in dealt if ROLE_FACTION[Role(r)] == Faction.MAFIA)
    assert mafia == bag_for(8).mafia


@pytest.mark.asyncio
async def test_secret_hides_roles_and_fast_shortens_timers(app: App) -> None:
    await app.store.set_chat_setting(-1, "mode", "secret")
    cfg = await app.game_cfg(-1)
    assert cfg["reveal_on_death"] is False and cfg["mode"] == "secret"
    await app.store.set_chat_setting(-1, "mode", "fast")
    cfg = await app.game_cfg(-1)
    assert cfg["timers"]["night"] == 25 and cfg["timers"]["day"] == 45
    assert cfg["reveal_on_death"] is True


@pytest.mark.asyncio
async def test_phase_uses_the_games_own_timer(app: App) -> None:
    g = _ready_game()
    g.timers = {"night": 33, "mute": 0}
    start(g)
    await app.persist(g)
    scheduled: list[float] = []
    app.schedule = lambda gid, seconds, factory: scheduled.append(seconds)  # type: ignore[method-assign]
    await app.enter_night(g)
    assert scheduled == [33]
    assert app.mute_on(g) is False


@pytest.mark.asyncio
async def test_config_outside_group_points_to_group(app: App) -> None:
    sent: list[str] = []
    msg = FakeMsg(SimpleNamespace(id=5), Chat(id=5, type=ChatType.PRIVATE), "/config", app.bot)

    async def answer(text, **k):
        sent.append(text)

    msg.answer = answer  # type: ignore[method-assign]
    await botmod.cmd_config(msg)  # type: ignore[arg-type]
    assert sent == [t("uz", "mafia.group_only")]


def _cfg_query(data: str, user_id: int = 100) -> SimpleNamespace:
    return SimpleNamespace(
        data=data,
        from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(chat=Chat(id=-77, type=ChatType.SUPERGROUP), edit_text=AsyncMock()),
        answer=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_config_changes_need_an_admin(app: App) -> None:
    q = _cfg_query("cfg:mode:chaos")
    await botmod.cb_config(q)  # type: ignore[arg-type]
    assert q.answer.await_args.args[0] == t("uz", "config.admin_only")
    assert (await app.chat_cfg(-77))["mode"] == "classic"


@pytest.mark.asyncio
async def test_admin_edits_mode_toggles_and_timers(app: App) -> None:
    app.bot.get_chat_member = AsyncMock(return_value=SimpleNamespace(status="administrator"))  # type: ignore[method-assign]
    for data in ("cfg:mode:chaos", "cfg:reveal", "cfg:mute", "cfg:day", "cfg:night"):
        await botmod.cb_config(_cfg_query(data))  # type: ignore[arg-type]
    cfg = await app.chat_cfg(-77)
    assert cfg == {"mode": "chaos", "reveal": False, "mute": False, "day": 120, "night": 60}
    await botmod.cb_config(_cfg_query("cfg:day"))  # type: ignore[arg-type]
    assert (await app.chat_cfg(-77))["day"] == 60  # cycles back
    bad = _cfg_query("cfg:mode:turbo")
    await botmod.cb_config(bad)  # type: ignore[arg-type]
    assert (await app.chat_cfg(-77))["mode"] == "chaos"


def test_lobby_shows_non_classic_mode() -> None:
    g = _ready_game()
    assert "🎲" not in texts.lobby_text(g, "bot")
    g.mode = "secret"
    assert t("uz", "mode.secret") in texts.lobby_text(g, "bot")


def test_config_text_marks_secret_as_hidden() -> None:
    text = texts.config_text({"mode": "secret", "reveal": True, "mute": True, "day": 90, "night": 45})
    assert t("uz", "mode.secret") in text and "❌" in text


def test_begin_night_helper_still_works() -> None:
    g = _ready_game()
    begin_night(g, 0, 10)
    assert g.deadline == 10
