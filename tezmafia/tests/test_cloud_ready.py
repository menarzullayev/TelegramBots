"""Cloud-safe operation: only production polls, /health for deploy checks, auto-deploy decisions."""

from __future__ import annotations

import pytest
from aiohttp.test_utils import TestClient, TestServer

from scripts.windows.autodeploy import decide
from tezmafia import bot as botmod


@pytest.mark.asyncio
async def test_bot_refuses_to_poll_without_the_production_flag(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)  # no .env here: a cloud copy with only the token
    monkeypatch.setenv("BOT_TOKEN", "1:TEST")
    monkeypatch.delenv("TEZMAFIA_PRODUCTION", raising=False)
    polled = []
    monkeypatch.setattr(botmod, "Bot", lambda *a, **k: polled.append("bot"))
    with pytest.raises(SystemExit) as exit_info:
        await botmod.run()
    assert exit_info.value.code == botmod.NOT_PRODUCTION != botmod.ALREADY_RUNNING  # supervisor keeps retrying
    assert polled == [] and not (tmp_path / "data").exists()  # stopped before the lock, the DB and Telegram


@pytest.mark.asyncio
async def test_health_reports_commit_and_uptime(tmp_path, monkeypatch) -> None:
    from tests.test_bot_e2e import FakeBot, _settings
    from tezmafia.bot import App
    from tezmafia.db import Store
    from tezmafia.webapp.server import build_app

    monkeypatch.chdir(tmp_path)
    store = Store(f"sqlite+aiosqlite:///{tmp_path}/t.db")
    await store.init()
    async with TestClient(TestServer(build_app(App(_settings(), store, FakeBot())))) as client:  # type: ignore[arg-type]
        r = await client.get("/health")
        body = await r.json()
        assert r.status == 200 and body["ok"] is True and body["commit"] and body["uptime_s"] >= 0
        assert r.headers["Cache-Control"] == "no-store"
        assert set(body) == {"ok", "commit", "started_at", "uptime_s"}  # nothing about users or config
    await store.engine.dispose()


@pytest.mark.parametrize(
    ("head", "remote", "touches_bot", "ci", "expected"),
    [
        ("a", "a", True, "success", "idle"),
        ("a", "b", False, "none", "pull"),  # docs or another project: pull without restarting the bot
        ("a", "b", True, "success", "deploy"),
        ("a", "b", True, "pending", "wait"),
        ("a", "b", True, "none", "wait"),  # CI not started yet
        ("a", "b", True, "failure", "skip"),  # red CI never reaches production
        ("a", "b", True, "cancelled", "skip"),
    ],
)
def test_autodeploy_only_ships_green_bot_changes(head, remote, touches_bot, ci, expected) -> None:
    assert decide(head, remote, touches_bot, ci) == expected
