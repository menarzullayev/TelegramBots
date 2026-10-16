"""Mini App design themes: state exposes the choice, POST /api/theme persists it, unknown ids are refused."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from tests.test_bot_e2e import FakeBot, _settings
from tests.test_webapp import init_data
from tezmafia import bot as botmod
from tezmafia.bot import App
from tezmafia.db import Store
from tezmafia.webapp.server import STATIC, THEMES, build_app, build_state

LOCALES = Path(__file__).resolve().parent.parent / "tezmafia" / "locales"
KEYS = ["theme.title", "theme.hint", *(f"theme.{t}" for t in THEMES)]


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
async def test_state_has_default_theme_and_the_list(app: App) -> None:
    s = await build_state(app, {"id": 7, "first_name": "Ann"})
    assert s["theme"] == "dossier"
    assert [x["id"] for x in s["themes"]] == list(THEMES) and len(THEMES) == 5
    assert all(x["name"] for x in s["themes"])
    assert s["strings"]["theme.title"] and s["strings"]["theme.hint"]


@pytest.mark.asyncio
async def test_post_theme_sets_and_persists(app: App) -> None:
    async with TestClient(TestServer(build_app(app))) as client:
        headers = {"Authorization": "tma " + init_data(7, token=app.settings.bot_token)}
        r = await client.post("/api/theme", json={"theme": "neon"}, headers=headers)
        assert r.status == 200
        body = await r.json()
        assert body["state"]["theme"] == "neon"
        again = await (await client.get("/api/state", headers=headers)).json()
        assert again["theme"] == "neon"
    assert await app.store.theme_of(7) == "neon"
    other = await build_state(app, {"id": 8, "first_name": "Bob"})
    assert other["theme"] == "dossier"  # per user
    await app.store.set_theme(7, "comic")  # change keeps the skins row intact
    assert (await app.store.skins_of(7))[0] == ""


@pytest.mark.asyncio
async def test_unknown_theme_is_rejected_and_nothing_changes(app: App) -> None:
    async with TestClient(TestServer(build_app(app))) as client:
        headers = {"Authorization": "tma " + init_data(7, token=app.settings.bot_token)}
        await client.post("/api/theme", json={"theme": "day"}, headers=headers)
        for bad in ({"theme": "laser"}, {"theme": ""}, {"theme": None}, {"theme": 3}, {"theme": ["neon"]}, {}, [], "neon"):
            r = await client.post("/api/theme", json=bad, headers=headers)
            assert r.status == 400, bad
        r = await client.post("/api/theme", data="not json", headers=headers)
        assert r.status == 400
    assert await app.store.theme_of(7) == "day"


@pytest.mark.asyncio
async def test_unsigned_and_forged_requests_are_401_and_writes_are_rate_limited(app: App) -> None:
    async with TestClient(TestServer(build_app(app))) as client:
        assert (await client.post("/api/theme", json={"theme": "neon"})).status == 401
        forged = {"Authorization": "tma " + init_data(7, token="1:wrong")}
        assert (await client.post("/api/theme", json={"theme": "neon"}, headers=forged)).status == 401
        headers = {"Authorization": "tma " + init_data(7, token=app.settings.bot_token)}
        codes = [(await client.post("/api/theme", json={"theme": "neon"}, headers=headers)).status for _ in range(60)]
        assert 429 in codes  # same limiter as the other write endpoints
    assert await app.store.theme_of(99) == ""


def test_a_stored_unknown_theme_falls_back_to_default() -> None:
    import asyncio

    class Stub:
        class store:  # noqa: N801
            @staticmethod
            async def theme_of(_uid: int) -> str:
                return "retired"

    from tezmafia.webapp.server import theme_of

    assert asyncio.run(theme_of(Stub, 1)) == "dossier"


def test_every_locale_has_the_theme_strings() -> None:
    for f in sorted(LOCALES.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        for key in KEYS:
            assert data.get(key, "").strip(), f"{f.name} missing {key}"


def test_page_defines_every_theme_and_the_early_bootstrap() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    for t in THEMES:
        assert f"{t}:" in html.split("window.tmTheme")[0], t  # bootstrap knows it (no flash)
        if t != "dossier":
            assert f'[data-theme="{t}"]' in html, t
    assert html.index("window.tmTheme(") < html.index("<style>")  # applied before first paint
