import json
from pathlib import Path

import pytest
from common.auth import hash_api_key
from common.runtime import in_memory_runtime, set_runtime
from common.testing import FakeHttpEvent

from functions.intake.handler import handle

TENANTS = Path(__file__).resolve().parents[3] / "tenants"


@pytest.fixture(autouse=True)
def rt(monkeypatch):
    monkeypatch.setenv("AP_SECRET_UNI_A_API_KEY", hash_api_key("key-a"))
    monkeypatch.setenv("AP_SECRET_UNI_B_API_KEY", hash_api_key("key-b"))
    runtime = in_memory_runtime(TENANTS)
    set_runtime(runtime)
    yield runtime
    set_runtime(None)


def _event(tenant="uni-a", key="key-a", app="app-1", body=b"\x89PNG data", **extra):
    headers = {
        "X-Tenant-Id": tenant,
        "X-Api-Key": key,
        "X-Application-Id": app,
        "Content-Type": "image/png",
        **extra,
    }
    return FakeHttpEvent(body=body, headers=headers)


def test_new_upload_returns_202_then_200(rt):
    first = handle(_event(), None)
    second = handle(_event(), None)
    assert first["statusCode"] == 202
    assert second["statusCode"] == 200
    assert json.loads(second["body"])["duplicate"] is True


def test_wrong_key_is_401_and_stores_nothing(rt):
    response = handle(_event(key="key-b"), None)
    assert response["statusCode"] == 401
    assert rt.storage.list("tenants/") == []


def test_bad_application_id_is_400():
    response = handle(_event(app="../../etc"), None)
    assert response["statusCode"] == 400


def test_unknown_declared_type_is_400():
    assert handle(_event(**{"X-Document-Type": "passport"}), None)["statusCode"] == 400


def test_get_is_405():
    assert handle(FakeHttpEvent(method="GET"), None)["statusCode"] == 405


def test_tenants_are_isolated(rt):
    handle(_event(tenant="uni-b", key="key-b"), None)
    assert rt.storage.list("tenants/uni-a/") == []
    assert len(rt.storage.list("tenants/uni-b/")) == 1
