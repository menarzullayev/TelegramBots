"""F6: Mini App API - initData authentication, state, invoices, badges, rate limit."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock
from urllib.parse import urlencode

import pytest
from aiohttp.test_utils import TestClient, TestServer

from tests.test_bot_e2e import FakeBot, _settings
from tezmafia import bot as botmod
from tezmafia.bot import App
from tezmafia.db import Store
from tezmafia.progress import ACHIEVEMENTS
from tezmafia.shop import STAR_PACKS, VIP_PERIOD
from tezmafia.webapp.server import RateLimit, authenticate, build_app

TOKEN = "1:TEST"  # same as _settings()


def init_data(user_id: int = 7, token: str = TOKEN, age: float = 0, lang: str = "en") -> str:
    """initData signed exactly as Telegram does (HMAC-SHA256 with the WebAppData secret)."""
    fields = {
        "auth_date": str(int(time.time() - age)),
        "query_id": "AAE",
        "user": json.dumps({"id": user_id, "first_name": "Ann", "language_code": lang}, separators=(",", ":")),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


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


@pytest.fixture
async def client(app: App):
    async with TestClient(TestServer(build_app(app))) as c:
        yield c


def _auth(**kw) -> dict[str, str]:
    return {"Authorization": "tma " + init_data(**kw)}


def test_authenticate_accepts_only_genuine_fresh_data() -> None:
    assert authenticate(TOKEN, "tma " + init_data())["id"] == 7
    assert authenticate(TOKEN, "tma " + init_data(token="2:OTHER")) is None  # forged with another token
    assert authenticate(TOKEN, "tma " + init_data(age=2 * 86400)) is None  # stale
    assert authenticate(TOKEN, init_data()) is None  # wrong scheme
    assert authenticate(TOKEN, None) is None
    tampered = init_data().replace("Ann", "Bob")
    assert authenticate(TOKEN, "tma " + tampered) is None


@pytest.mark.asyncio
async def test_page_is_served_with_security_headers(client: TestClient) -> None:
    resp = await client.get("/")
    assert resp.status == 200 and "telegram-web-app.js" in await resp.text()
    assert resp.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.asyncio
async def test_state_requires_valid_init_data(client: TestClient) -> None:
    assert (await client.get("/api/state")).status == 401
    assert (await client.get("/api/state", headers={"Authorization": "tma junk"})).status == 401


@pytest.mark.asyncio
async def test_state_returns_profile_achievements_top_and_shop(app: App, client: TestClient) -> None:
    await app.store.bump_stat(7, "Ann", won=True, alive=True)
    await app.store.award(7, {"first_game", "first_win"})
    resp = await client.get("/api/state", headers=_auth(lang="ru"))
    assert resp.status == 200
    data = await resp.json()
    assert data["lang"] == "ru"  # no stored preference: Telegram's language is used
    assert data["profile"]["games"] == 1 and data["profile"]["xp"] == 35
    assert len(data["achievements"]) == len(ACHIEVEMENTS)
    assert {a["key"] for a in data["achievements"] if a["unlocked"]} == {"first_game", "first_win"}
    assert [p["key"] for p in data["shop"]["packs"]] == list(STAR_PACKS)
    assert data["top"]["all"]["rows"][0]["name"] == "Ann"


@pytest.mark.asyncio
async def test_invoice_is_created_for_the_caller(app: App, client: TestClient) -> None:
    app.bot.create_invoice_link = AsyncMock(return_value="https://t.me/$inv")  # type: ignore[attr-defined]
    resp = await client.post("/api/invoice", json={"product": "c450"}, headers=_auth())
    assert (await resp.json()) == {"link": "https://t.me/$inv"}
    kw = app.bot.create_invoice_link.await_args.kwargs
    assert kw["payload"] == "c450:7" and kw["currency"] == "XTR" and "subscription_period" not in kw
    await client.post("/api/invoice", json={"product": "vip"}, headers=_auth())
    assert app.bot.create_invoice_link.await_args.kwargs["subscription_period"] == VIP_PERIOD
    bad = await client.post("/api/invoice", json={"product": "gold"}, headers=_auth())
    assert bad.status == 400
    anon = await client.post("/api/invoice", json={"product": "c450"})
    assert anon.status == 401


@pytest.mark.asyncio
async def test_badge_purchase_and_removal(app: App, client: TestClient) -> None:
    resp = await client.post("/api/badge", json={"key": "star"}, headers=_auth())
    assert (await resp.json())["result"] == "no_gems"
    await app.store.credit_wallet(7, "Ann", gems=5)
    data = await (await client.post("/api/badge", json={"key": "star"}, headers=_auth())).json()
    assert data["result"] == "bought" and data["state"]["profile"]["badge"] == "⭐"
    data = await (await client.post("/api/badge", json={"key": "off"}, headers=_auth())).json()
    assert data["state"]["profile"]["badge"] == ""
    assert (await client.post("/api/badge", json={"key": "nope"}, headers=_auth())).status == 400


@pytest.mark.asyncio
async def test_write_calls_are_rate_limited(app: App, client: TestClient) -> None:
    client.server.app["limits"] = RateLimit(limit=2, window=60)
    for _ in range(2):
        assert (await client.post("/api/badge", json={"key": "off"}, headers=_auth())).status == 200
    assert (await client.post("/api/badge", json={"key": "off"}, headers=_auth())).status == 429
    # Another user has their own budget.
    assert (await client.post("/api/badge", json={"key": "off"}, headers=_auth(user_id=8))).status == 200


@pytest.mark.asyncio
async def test_app_command_needs_a_public_url(app: App) -> None:
    from types import SimpleNamespace

    from aiogram.enums import ChatType
    from aiogram.types import Chat

    from tezmafia.i18n import t

    sent: list[tuple[str, dict]] = []
    msg = SimpleNamespace(chat=Chat(id=7, type=ChatType.PRIVATE), answer=AsyncMock(side_effect=lambda txt, **k: sent.append((txt, k))))
    await botmod.cmd_app(msg)  # type: ignore[arg-type]
    assert sent[-1][0] == t("uz", "app.error")
    app.settings.webapp_url = "https://mafia.example/"
    await botmod.cmd_app(msg)  # type: ignore[arg-type]
    button = sent[-1][1]["reply_markup"].inline_keyboard[0][0]
    assert button.web_app.url == "https://mafia.example/"
    group = SimpleNamespace(chat=Chat(id=-1, type=ChatType.SUPERGROUP), answer=msg.answer)
    await botmod.cmd_app(group)  # type: ignore[arg-type]
    assert sent[-1][1]["reply_markup"].inline_keyboard[0][0].url.endswith("?start=app")
