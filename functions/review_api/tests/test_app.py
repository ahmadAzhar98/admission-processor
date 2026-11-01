import pytest
from common.auth import hash_api_key
from fastapi.testclient import TestClient

from functions.review_api.app import create_app

HEADERS = {"X-Tenant-Id": "uni-b", "X-Api-Key": "staff-b"}


@pytest.fixture
def client(rt, monkeypatch):
    monkeypatch.setenv("AP_SECRET_UNI_B_STAFF_KEY", hash_api_key("staff-b"))
    monkeypatch.setenv("AP_SECRET_UNI_B_API_KEY", hash_api_key("upload-b"))
    return TestClient(create_app(lambda: rt))


def test_requires_staff_credentials(client):
    assert client.get("/reviews").status_code == 401
    upload_key = {"X-Tenant-Id": "uni-b", "X-Api-Key": "upload-b"}
    assert client.get("/reviews", headers=upload_key).status_code == 401
    assert client.get("/healthz").json() == {"status": "ok"}


def test_list_detail_and_image(client):
    [row] = client.get("/reviews", headers=HEADERS).json()
    assert row["document_id"] == "d1"
    detail = client.get("/reviews/d1", headers=HEADERS).json()
    assert detail["item"]["reasons"] == ["low_confidence"]
    image = client.get("/documents/d1/image", headers=HEADERS)
    assert image.content == b"PNG" and image.headers["content-type"] == "image/png"


def test_resolve_and_audit_trail(client):
    body = {"outcome": "approve", "reviewer": "staff.2", "corrections": {"district": "Lahore"}}
    response = client.post("/reviews/d1/resolve", json=body, headers=HEADERS)
    assert response.status_code == 200 and response.json()["status"] == "resolved"
    again = client.post("/reviews/d1/resolve", json=body, headers=HEADERS)
    assert again.status_code == 400
    actions = [e["action"] for e in client.get("/documents/d1/audit", headers=HEADERS).json()]
    assert actions[-1] == "review_resolved"


def test_unknown_document_is_404(client):
    assert client.get("/reviews/nope", headers=HEADERS).status_code == 404


def test_bad_resolution_body_is_422(client):
    response = client.post("/reviews/d1/resolve", json={"outcome": "maybe"}, headers=HEADERS)
    assert response.status_code == 422
