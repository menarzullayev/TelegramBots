"""Import/boot smoke checks: database, Gemini analyzer (real SDK over a mock transport), reporter, dashboard, scraper."""

import asyncio
import json
import os

import httpx2
import pytest
from google import genai
from google.genai import types

from modules.database import db

# pyrogram resolves an event loop when it is first imported, so import it before any test runs asyncio.run().
from modules.scraper import scraper  # noqa: E402
from pyrogram import Client  # noqa: E402

CHAT = -100123


@pytest.fixture(autouse=True)
def _clean_members():
    db.cursor.execute("DELETE FROM members")
    db.conn.commit()
    yield


def _seed():
    db.add_or_update_member(1, CHAT, "Ali", "Valiyev", "ali_v")
    db.add_or_update_member(2, CHAT, "Madina", "Karimova", "madina_k")
    db.add_or_update_member(3, CHAT, None, None, None, is_deleted=True)


def test_database_roundtrip():
    _seed()
    assert len(db.get_unanalyzed_members(CHAT)) >= 2
    db.update_gender(1, CHAT, "Male")
    db.update_gender(2, CHAT, "Female")
    stats = db.get_stats(CHAT)
    assert stats["Male"] == 1
    assert stats["Female"] == 1


def _gemini_client(handler) -> genai.Client:
    return genai.Client(
        api_key="test-key",
        http_options=types.HttpOptions(client_args={"transport": httpx2.MockTransport(handler)}),
    )


def test_analyzer_parses_gemini_response_with_real_sdk(monkeypatch):
    from modules.analyzer import analyzer

    _seed()
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        answer = json.dumps({"1": "Male", "2": "Female"})
        return httpx2.Response(
            200,
            json={
                "candidates": [{"content": {"role": "model", "parts": [{"text": answer}]}, "finishReason": "STOP"}],
                "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 5, "totalTokenCount": 10},
            },
        )

    monkeypatch.setattr(analyzer, "client", _gemini_client(handler))
    batch = [m for m in db.get_unanalyzed_members(CHAT) if m[0] in (1, 2)]
    asyncio.run(analyzer._process_batch(CHAT, batch, retries=1))

    assert analyzer.model_name in seen["path"]
    assert seen["body"]["generationConfig"]["responseMimeType"] == "application/json"
    stats = db.get_stats(CHAT)
    assert stats["Male"] == 1
    assert stats["Female"] == 1


def test_reporter_writes_png(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from modules.reporter import Reporter

    _seed()
    db.update_gender(1, CHAT, "Male")
    text, path = Reporter().generate_report(CHAT, "Test chat")
    assert "Test chat" in text
    assert os.path.exists(path)
    with open(path, "rb") as fh:
        assert fh.read(8) == b"\x89PNG\r\n\x1a\n"


def test_dashboard_api_routes():
    from dashboard.app import app

    _seed()
    db.update_gender(1, CHAT, "Male")
    client = app.test_client()
    stats = client.get(f"/api/stats/{CHAT}")
    assert stats.status_code == 200
    assert stats.get_json()["Male"] == 1

    members = client.get(f"/api/members/{CHAT}?limit=10")
    assert members.status_code == 200
    assert members.get_json()["total"] >= 2


def test_scraper_client_is_constructed():
    assert isinstance(scraper.app, Client)
