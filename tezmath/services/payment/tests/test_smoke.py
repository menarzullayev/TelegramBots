"""Boot smoke checks for the payment service (FastAPI app + routers import)."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://u:p@localhost:5432/d")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("INTERNAL_API_KEY", "test-internal-key")

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

ORDER = {"user_id": 1, "method": "payme", "amount": 1000, "period": "monthly"}


def test_health():
    resp = TestClient(app).get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_webhook_status_route():
    resp = TestClient(app).get("/api/v1/webhooks/status")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_order_creation_requires_internal_key():
    client = TestClient(app)
    assert client.post("/api/v1/orders", json=ORDER).status_code == 422  # missing X-Internal-Key header
    assert client.post("/api/v1/orders", headers={"X-Internal-Key": "wrong"}, json=ORDER).status_code == 403
