"""Boot smoke checks for the renderer (FastAPI + matplotlib + boto3)."""

import main
from fastapi.testclient import TestClient

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_health():
    resp = TestClient(main.app).get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_latex_to_png_returns_png_bytes():
    data = main.latex_to_png(r"x^2 + \frac{1}{2} = 5", dpi=50)
    assert data.startswith(PNG_MAGIC)
    assert len(data) > 200


def test_render_endpoint_uploads_png(monkeypatch):
    uploaded = {}

    def fake_upload(data: bytes, filename: str) -> str:
        uploaded["data"], uploaded["filename"] = data, filename
        return f"http://cdn.test/{filename}"

    monkeypatch.setattr(main, "upload_to_s3", fake_upload)
    resp = TestClient(main.app).post("/render", json={"latex": r"\alpha + \beta", "dpi": 50})
    assert resp.status_code == 200
    body = resp.json()
    assert body["url"] == f"http://cdn.test/{body['filename']}"
    assert uploaded["data"].startswith(PNG_MAGIC)


def test_upload_to_s3_builds_boto3_call(monkeypatch):
    calls = {}

    class FakeS3:
        def put_object(self, **kwargs):
            calls.update(kwargs)

    monkeypatch.setattr(main.boto3, "client", lambda *a, **k: FakeS3())
    url = main.upload_to_s3(b"png", "a.png")
    assert calls["Key"] == "renders/a.png"
    assert calls["ContentType"] == "image/png"
    assert url.endswith("/renders/a.png")


def test_render_endpoint_validates_body():
    resp = TestClient(main.app).post("/render", json={"latex": None})
    assert resp.status_code == 422
