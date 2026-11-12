"""Boot/auth smoke checks for the admin panel (FastAPI + PyJWT)."""

import hashlib
import os

os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-0123")
os.environ.setdefault("ADMIN_PASSWORD_HASH", hashlib.sha256(b"s3cret").hexdigest())
os.environ.setdefault("DATABASE_URL", "postgresql://u:p@localhost:5432/d")

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_login_rejects_wrong_password(client):
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_login_issues_verifiable_jwt(client):
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "s3cret"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    claims = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
    assert claims["sub"] == "admin"
    assert claims["exp"] > claims["iat"]


def test_protected_route_without_token_is_unauthorized(client):
    # fastapi >= 0.122 answers a missing bearer token with 401 (older releases used 403)
    assert client.get("/api/v1/users").status_code == 401


def test_verify_token_rejects_garbage_and_accepts_issued_token():
    from auth import create_token, verify_token
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    good = HTTPAuthorizationCredentials(scheme="Bearer", credentials=create_token("admin"))
    assert verify_token(good) == "admin"

    bad = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not-a-token")
    with pytest.raises(HTTPException) as exc:
        verify_token(bad)
    assert exc.value.status_code == 401
