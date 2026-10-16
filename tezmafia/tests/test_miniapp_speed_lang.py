"""Mini App speed (self-hosted fonts, cacheable page), language picker endpoint and icon sprite."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from tests.test_bot_e2e import FakeBot, _settings
from tests.test_webapp import init_data
from tezmafia import bot as botmod
from tezmafia.bot import App
from tezmafia.db import Store
from tezmafia.i18n import ALLOWED
from tezmafia.webapp.server import LANG_NAMES, STATIC, build_app, build_state

ROOT = Path(__file__).resolve().parent.parent
LOCALES = ROOT / "tezmafia" / "locales"
FONTS = ROOT / "assets" / "fonts"


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


def _h(app: App, uid: int = 7, lang: str = "en") -> dict[str, str]:
    return {"Authorization": "tma " + init_data(uid, token=app.settings.bot_token, lang=lang)}


# --- /api/lang -------------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lang_sets_persists_and_state_comes_back_translated(app: App) -> None:
    async with TestClient(TestServer(build_app(app))) as client:
        before = await (await client.get("/api/state", headers=_h(app))).json()
        assert before["lang"] == "en"  # first guess: Telegram language_code
        r = await client.post("/api/lang", json={"lang": "ru"}, headers=_h(app))
        assert r.status == 200
        body = await r.json()
        assert body["state"]["lang"] == "ru"
        assert body["state"]["strings"]["lang.title"] == "Язык"
        assert body["state"]["strings"]["app.tab_log"] != before["strings"]["app.tab_log"]
        again = await (await client.get("/api/state", headers=_h(app))).json()
        assert again["lang"] == "ru"
    assert await app.store.get_lang(7) == "ru"  # the very row the bot's /lang buttons read
    assert await app.store.get_lang(8) == "uz"  # per user


@pytest.mark.asyncio
async def test_saved_uzbek_beats_telegram_language_code(app: App) -> None:
    """A user who explicitly picked Uzbek must not be flipped back to English by Telegram's language_code."""
    user = {"id": 7, "first_name": "Ann", "language_code": "en"}
    assert (await build_state(app, user))["lang"] == "en"
    await app.store.set_lang(7, "uz")
    assert (await build_state(app, user))["lang"] == "uz"
    await app.store.set_lang(7, "tr")
    assert (await build_state(app, user))["lang"] == "tr"


@pytest.mark.asyncio
async def test_unknown_language_is_400_and_nothing_changes(app: App) -> None:
    async with TestClient(TestServer(build_app(app))) as client:
        await client.post("/api/lang", json={"lang": "tr"}, headers=_h(app))
        for bad in ({"lang": "xx"}, {"lang": ""}, {"lang": None}, {"lang": 3}, {"lang": ["ru"]}, {"lang": "RU"}, {}, [], "ru"):
            r = await client.post("/api/lang", json=bad, headers=_h(app, uid=7))
            assert r.status == 400, bad
        assert (await client.post("/api/lang", data="not json", headers=_h(app, uid=8))).status == 400  # own rate-limit bucket
    assert await app.store.get_lang(7) == "tr"


@pytest.mark.asyncio
async def test_lang_unsigned_forged_and_rate_limited(app: App) -> None:
    async with TestClient(TestServer(build_app(app))) as client:
        assert (await client.post("/api/lang", json={"lang": "ru"})).status == 401
        forged = {"Authorization": "tma " + init_data(7, token="1:wrong")}
        assert (await client.post("/api/lang", json={"lang": "ru"}, headers=forged)).status == 401
        codes = [(await client.post("/api/lang", json={"lang": "ru"}, headers=_h(app))).status for _ in range(60)]
        assert 429 in codes  # same limiter as the other write endpoints
    assert await app.store.lang_pref(99) is None


@pytest.mark.asyncio
async def test_state_lists_all_languages_with_native_names(app: App) -> None:
    s = await build_state(app, {"id": 7, "first_name": "Ann"})
    assert {x["code"] for x in s["languages"]} == set(ALLOWED) == set(LANG_NAMES) and len(s["languages"]) == 11
    names = {x["code"]: x["name"] for x in s["languages"]}
    assert names["uz"] == "O‘zbekcha" and names["ru"] == "Русский" and names["br"] == "Português (BR)"


def test_every_locale_has_the_new_strings() -> None:
    for f in sorted(LOCALES.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        for key in ("lang.title", "app.close"):
            assert data.get(key, "").strip(), f"{f.name} missing {key}"


# --- fonts -----------------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_font_route_serves_woff2_immutable(app: App) -> None:
    name = "pt-mono-latin-400.woff2"
    async with TestClient(TestServer(build_app(app))) as client:
        r = await client.get(f"/assets/fonts/{name}")
        assert r.status == 200
        assert r.headers["Content-Type"] == "font/woff2"
        assert "immutable" in r.headers["Cache-Control"] and "max-age=31536000" in r.headers["Cache-Control"]
        assert (await r.read())[:4] == b"wOF2"


@pytest.mark.asyncio
async def test_font_route_rejects_traversal_and_non_fonts(app: App) -> None:
    async with TestClient(TestServer(build_app(app))) as client:
        for bad in (
            "..%2fraven%2froles%2fmafia.jpg", "%2e%2e/%2e%2e/tezmafia/webapp/server.py",
            "..%5c..%5cserver.py", "pt-mono-latin-400.woff", "pt-mono-latin-400.woff2.txt", "PT-MONO.woff2", "missing.woff2",
            "pt-mono-latin-400.woff2/../../x.woff2", ".woff2", "a.jpg", "x.py",
        ):
            r = await client.get(f"/assets/fonts/{bad}")
            assert r.status == 404, (bad, r.status)


def test_every_font_face_points_at_a_committed_file_and_nothing_external() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    urls = re.findall(r"url\(/assets/fonts/([a-z0-9-]+\.woff2)\)", html)
    assert len(urls) >= 40
    for u in urls:
        assert (FONTS / u).is_file(), u
    assert "font-display:swap" in html
    for u in re.findall(r'rel="preload" href="/assets/fonts/([^"]+)"', html):
        assert (FONTS / u).is_file(), u


# --- page ------------------------------------------------------------------------------------------------------


def test_page_has_no_google_fonts_and_no_native_select() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in html and "fonts.gstatic.com" not in html
    assert "preconnect" not in html
    assert not re.search(r"<select\b", html, re.I) and "createElement(\"select\")" not in html


def test_page_starts_state_early_and_loads_telegram_sdk_async() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    head = html.split("</head>")[0]
    assert "tgWebAppData" in head and "/api/state" in head  # the fetch starts in <head>
    assert re.search(r'<script async src="https://telegram\.org/js/telegram-web-app\.js"', head)
    assert not re.search(r'<script src="https://telegram', html)  # never render-blocking
    body = html.split("<body>")[1]
    assert 'class="sk' in body.split("<script>")[0]  # a skeleton exists in static HTML


def test_page_uses_the_sprite_for_core_icons() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    symbols = set(re.findall(r'<symbol id="i-([a-z]+)"', html))
    used = set(re.findall(r'(?<![a-zA-Z])ic\("([a-z]+)"', html)) | set(re.findall(r'(?:act\((?:[^,]*), "([a-z]+)")', html))
    assert {"dossier", "roles", "wanted", "log", "market", "coin", "gem", "star", "trophy", "shield", "globe", "check"} <= symbols
    assert used - {"id"} <= symbols, used - symbols  # every referenced icon exists in the sprite
    assert "currentColor" in html and "--icon-sw" in html
    for emoji in ("💎", "✕", "⚠️"):  # content emojis only; these were UI glyphs
        assert emoji not in html


@pytest.mark.asyncio
async def test_index_has_etag_and_answers_304(app: App) -> None:
    async with TestClient(TestServer(build_app(app))) as client:
        r = await client.get("/")
        assert r.status == 200
        etag = r.headers["ETag"]
        assert etag and "max-age" in r.headers["Cache-Control"]
        r2 = await client.get("/", headers={"If-None-Match": etag})
        assert r2.status == 304
        r3 = await client.get("/", headers={"If-None-Match": '"stale"'})
        assert r3.status == 200  # negative: a different validator gets the full page
