"""H3: role-card skins bought with gems, used on role DMs and result cards (DECISION-17)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests.test_bot_e2e import FakeBot, _ready_game, _settings
from tezmafia import bot as botmod
from tezmafia.bot import App
from tezmafia.brand import ASSETS, role_card
from tezmafia.db import Store
from tezmafia.engine import Phase, start
from tezmafia.i18n import t
from tezmafia.roles import Role
from tezmafia.shop import SKIN_COST, SKINS


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


def test_every_role_has_every_skin_and_a_preview() -> None:
    for skin in SKINS:
        for role in Role:
            assert role_card(role.value, skin) == f"raven/skins/{skin}/{role.value}.jpg"
            assert (ASSETS / role_card(role.value, skin)).is_file()
    assert (ASSETS / "raven" / "skins" / "preview.jpg").is_file()
    assert role_card("mafia", "") == role_card("mafia", "unknown") == "raven/roles/mafia.jpg"  # falls back
    assert role_card("nobody", "noir") is None


@pytest.mark.asyncio
async def test_buy_wear_and_take_off(app: App) -> None:
    assert await app.store.buy_skin(7, "A", "noir", SKIN_COST) == "no_gems"
    assert await app.store.skins_of(7) == ("", [])  # a failed purchase grants nothing
    await app.store.credit_wallet(7, "A", gems=SKIN_COST + 3)
    assert await app.store.buy_skin(7, "A", "noir", SKIN_COST) == "bought"
    assert (await app.store.get_account(7))["gems"] == 3
    assert await app.store.buy_skin(7, "A", "noir", SKIN_COST) == "owned"  # wearing again is free
    assert (await app.store.get_account(7))["gems"] == 3
    assert await app.store.buy_skin(7, "A", "gold", SKIN_COST) == "no_gems"
    assert await app.store.buy_skin(7, "A", "laser", SKIN_COST) == "no_item"
    await app.store.take_off_skin(7)
    assert await app.store.skins_of(7) == ("", ["noir"])
    await app.store.grant_skin(7, "neon")  # pass reward: owned, not worn
    assert await app.store.skins_of(7) == ("", ["neon", "noir"])
    await app.store.delete_user(7)
    assert await app.store.skins_of(7) == ("", [])


@pytest.mark.asyncio
async def test_role_dm_and_result_card_use_the_skin(app: App, monkeypatch) -> None:
    await app.store.credit_wallet(100, "P0", gems=SKIN_COST)
    await app.store.buy_skin(100, "P0", "gold", SKIN_COST)
    sent: list[tuple[int, str | None]] = []

    async def dm_photo(uid, name, text, **k):
        sent.append((uid, name))
        return True

    app.dm_photo = dm_photo  # type: ignore[method-assign]
    g = _ready_game(5)
    start(g)
    await app.send_role_dms(g)
    by_user = dict(sent)
    assert by_user[100].startswith("raven/skins/gold/") and by_user[101].startswith("raven/roles/")

    seen: list[str] = []
    import tezmafia.cards as cards

    real = cards.result_card

    def spy(*a, **k):
        seen.append(a[6] if len(a) > 6 else k.get("skin", ""))
        return real(*a, **k)

    monkeypatch.setattr(cards, "result_card", spy)
    g.winner, g.phase = "town", Phase.FINISHED
    app.dm = AsyncMock(return_value=True)  # type: ignore[method-assign]
    await app.send_card(g, g.by_user(100), True, {"games": 1, "wins": 1, "xp": 40})
    await app.send_card(g, g.by_user(101), True, {"games": 1, "wins": 1, "xp": 40})
    assert seen == ["gold", ""]


@pytest.mark.asyncio
async def test_skin_buttons_and_mini_app(app: App) -> None:
    from tezmafia.keyboards import skins_kb
    from tezmafia.webapp.server import build_state

    rows = [r[0].callback_data for r in skins_kb([], "").inline_keyboard]
    assert rows == [f"sk:{k}" for k in SKINS]
    worn = skins_kb(["noir"], "noir").inline_keyboard
    assert worn[0][0].text.startswith("✓") and worn[-1][0].callback_data == "sk:off"
    await app.store.credit_wallet(100, "P0", gems=SKIN_COST)
    await app.store.buy_skin(100, "P0", "neon", SKIN_COST)
    state = await build_state(app, {"id": 100, "first_name": "P0"})
    items = {i["key"]: i for i in state["skins"]["items"]}
    assert items["neon"]["owned"] and items["neon"]["worn"] and not items["noir"]["owned"]
    assert str(SKIN_COST) in items["noir"]["label"]


@pytest.mark.asyncio
async def test_skin_callback(app: App) -> None:
    await app.store.credit_wallet(100, "P0", gems=SKIN_COST)
    answers: list[str] = []
    msg = SimpleNamespace(edit_caption=AsyncMock(), answer=AsyncMock())

    def query(data: str):
        return SimpleNamespace(
            data=data, from_user=SimpleNamespace(id=100, first_name="P0"), message=msg,
            answer=AsyncMock(side_effect=lambda text=None, **k: answers.append(text)),
        )

    await botmod.cb_skin(query("sk:gold"))  # type: ignore[arg-type]
    assert answers[-1] == t("uz", "skins.bought")
    await botmod.cb_skin(query("sk:noir"))  # type: ignore[arg-type]
    assert answers[-1] == t("uz", "gems.no_gems")
    await botmod.cb_skin(query("sk:off"))  # type: ignore[arg-type]
    assert answers[-1] == t("uz", "skins.removed") and (await app.store.skins_of(100))[0] == ""
