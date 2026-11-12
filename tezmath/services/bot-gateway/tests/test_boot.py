"""Boot smoke checks for bot-gateway: JSON logging, handler registration, wire format of the Claude call."""

import json
import logging
import os

os.environ.setdefault("BOT_TOKEN", "123456:ABCDEF-fake-token-for-tests")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

import pytest  # noqa: E402


def test_setup_logging_emits_json(capsys):
    from middleware.logger import setup_logging

    root = logging.getLogger()
    before = list(root.handlers)
    try:
        setup_logging("INFO")
        logging.getLogger("tezmath.test").info("hello json")
        out = capsys.readouterr().out.strip().splitlines()[-1]
        record = json.loads(out)
        assert record["message"] == "hello json"
        assert record["levelname"] == "INFO"
        assert record["name"] == "tezmath.test"
    finally:
        for h in list(root.handlers):
            if h not in before:
                root.removeHandler(h)


def test_build_application_registers_handlers():
    from main import build_application

    app = build_application()
    assert sum(len(group) for group in app.handlers.values()) >= 12


@pytest.mark.asyncio
async def test_publish_solver_task_wire_format_against_real_sdk_client(monkeypatch):
    import anthropic
    import httpx2

    from services import queue_producer

    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx2.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "claude-sonnet-4-6",
                "content": [{"type": "text", "text": "Javob: 5"}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 7, "output_tokens": 9},
            },
        )

    client = anthropic.AsyncAnthropic(
        api_key="test-key", http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    )
    saved = {}

    async def fake_save_solution(**kwargs):
        saved.update(kwargs)
        return 99

    monkeypatch.setattr(queue_producer, "_get_client", lambda: client)
    monkeypatch.setattr(queue_producer, "save_solution", fake_save_solution)

    result = await queue_producer.publish_solver_task(
        user_id=1, telegram_id=2, input_type="text", content="x+3=8", lang="uz"
    )

    assert seen["path"] == "/v1/messages"
    assert seen["body"]["max_tokens"] == 8192
    assert result["solution_id"] == 99
    assert result["solution_text"] == "Javob: 5"
    assert saved["tokens_used"] == 16
