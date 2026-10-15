"""Mini App redesign (case file): new state blocks, daily claim, role portraits route."""

from __future__ import annotations

import pytest
from aiohttp.test_utils import TestClient, TestServer

from tests.test_bot_e2e import FakeBot, _settings
from tests.test_webapp import init_data
from tezmafia import bot as botmod
from tezmafia.bot import App
from tezmafia.db import Store
from tezmafia.webapp.server import build_app, build_state


@pytest.fixture
async def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    store = Store(f"sqlite+aiosqlite:///{tmp_path}/data/t.db")
    await store.init()
    application = App(_settings(), store, FakeBot())  # type: ignore[arg-type]
    botmod.app = application
    yield application
    await store.engine.dispose()


@pytest.mark.asyncio
async def test_state_has_the_case_file_blocks(app: App) -> None:
    await app.store.credit_wallet(7, "Ann", coins=5)
    s = await build_state(app, {"id": 7, "first_name": "Ann"})
    assert s["case"].endswith("00007")
    assert {"title", "claimed", "button", "done", "streak_text"} <= set(s["daily"]) and s["daily"]["claimed"] is False
    assert len(s["quests"]["items"]) == 3 and all({"title", "progress", "target"} <= set(q) for q in s["quests"]["items"])
    assert len(s["roles"]["items"]) == 21 and s["roles"]["items"][0]["image"].startswith("/assets/raven/roles/")
    assert s["clan"]["mine"] is None and s["tournament"]["rows"] == []
    assert s["profile"]["lines"]["record"] and s["profile"]["lines"]["purse"] and s["profile"]["lines"]["fair_score"] == "100"
    for key in ("app.tab_dossier", "app.tab_roles", "app.tab_wanted", "app.tab_log", "app.tab_market", "app.stamp"):
        assert s["strings"][key]


@pytest.mark.asyncio
async def test_role_portraits_follow_the_worn_skin(app: App) -> None:
    await app.store.credit_wallet(7, "Ann", gems=20)
    await app.store.buy_skin(7, "Ann", "neon", 20)
    s = await build_state(app, {"id": 7, "first_name": "Ann"})
    assert all(r["image"].startswith("/assets/raven/skins/neon/") for r in s["roles"]["items"])


@pytest.mark.asyncio
async def test_daily_claim_api_once_and_assets_route(app: App) -> None:
    async with TestClient(TestServer(build_app(app))) as client:
        headers = {"Authorization": "tma " + init_data(7, token=app.settings.bot_token)}
        r1 = await (await client.post("/api/daily", json={}, headers=headers)).json()
        r2 = await (await client.post("/api/daily", json={}, headers=headers)).json()
        assert r1["result"] == "claimed" and r1["state"]["daily"]["claimed"] is True
        assert r2["result"] == "already"
        assert (await client.post("/api/daily", json={})).status == 401  # unsigned requests are refused

        ok = await client.get("/assets/raven/roles/mafia.jpg")
        assert ok.status == 200 and ok.headers["Content-Type"] == "image/jpeg"
        assert (await client.get("/assets/raven/skins/gold/don.jpg")).status == 200
        for bad in ("/assets/raven/roles/../../tezmafia/config.py", "/assets/raven/banner.jpg",
                    "/assets/raven/skins/laser/mafia.jpg", "/assets/raven/roles/nobody.jpg"):
            assert (await client.get(bad)).status == 404, bad  # only role portraits and skins are served
