"""Import/boot smoke checks for the notification worker (aio-pika, asyncpg, httpx)."""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
os.environ.setdefault("DATABASE_URL", "postgresql://u:p@localhost:5432/d")
os.environ.setdefault("BOT_TOKEN", "123456:fake-token")

import httpx  # noqa: E402
import pytest  # noqa: E402
import worker  # noqa: E402


def _patched_client(handler):
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    return patch.object(worker.httpx, "AsyncClient", lambda **kw: real_client(transport=transport, **kw))


def test_worker_exposes_queue_and_consumer():
    assert worker.BROADCAST_QUEUE == "notification.broadcast"
    assert callable(worker.process_broadcast)
    assert worker.TELEGRAM_API.endswith("/bot" + os.environ["BOT_TOKEN"])


@pytest.mark.asyncio
async def test_send_message_posts_to_telegram():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True})

    with _patched_client(handler):
        assert await worker.send_message(42, "hi") is True

    assert seen["url"].endswith("/sendMessage")
    assert seen["body"]["chat_id"] == 42


@pytest.mark.asyncio
async def test_send_message_reports_failure_status():
    with _patched_client(lambda request: httpx.Response(403, json={"ok": False})):
        assert await worker.send_message(42, "hi") is False


@pytest.mark.asyncio
async def test_process_broadcast_sends_to_every_user():
    message = MagicMock()
    message.body = json.dumps({"message": "hello", "job_id": "j1"}).encode()
    message.process.return_value.__aenter__ = AsyncMock(return_value=None)
    message.process.return_value.__aexit__ = AsyncMock(return_value=False)

    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[{"telegram_id": 1}, {"telegram_id": 2}])
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    send = AsyncMock(return_value=True)
    with (
        patch.object(worker, "get_pool", AsyncMock(return_value=pool)),
        patch.object(worker, "send_message", send),
        patch.object(worker, "DELAY_BETWEEN_BATCHES", 0),
    ):
        await worker.process_broadcast(message)

    assert [c.args[0] for c in send.call_args_list] == [1, 2]
