import json
from pathlib import Path

import pytest
from common.auth import hash_api_key
from common.runtime import in_memory_runtime, set_runtime
from common.schemas.documents import Document
from common.schemas.events import PipelineEvent
from common.testing import FakeHttpEvent
from PIL import ImageFilter

from functions.quality_check.handler import handle

TENANTS = Path(__file__).resolve().parents[3] / "tenants"


@pytest.fixture(autouse=True)
def rt(monkeypatch):
    monkeypatch.setenv("AP_SECRET_UNI_C_API_KEY", hash_api_key("key-c"))
    runtime = in_memory_runtime(TENANTS)
    set_runtime(runtime)
    yield runtime
    set_runtime(None)


def _precheck(data: bytes, key: str = "key-c") -> FakeHttpEvent:
    return FakeHttpEvent(
        body=data,
        headers={"Content-Type": "image/png", "X-Tenant-Id": "uni-c", "X-Api-Key": key},
    )


def test_precheck_returns_report(page_bytes):
    response = handle(_precheck(page_bytes()), None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert body["reupload_required"] is False


def test_precheck_flags_blurry_upload(page_bytes):
    blurred = page_bytes(transform=lambda im: im.filter(ImageFilter.GaussianBlur(4)))
    body = json.loads(handle(_precheck(blurred), None)["body"])
    assert body["reupload_required"] is True
    assert "blurry" in body["issues"]


def test_precheck_requires_credentials(page_bytes):
    assert handle(_precheck(page_bytes(), key="nope"), None)["statusCode"] == 401


def test_pipeline_event_is_processed(rt, page_bytes):
    data = page_bytes()
    key = rt.tenant_storage("uni-c").put(("applications", "a1", "d1.png"), data, "image/png")
    rt.documents.add(
        Document(
            tenant_id="uni-c",
            document_id="d1",
            application_id="a1",
            object_key=key,
            content_type="image/png",
            sha256="1" * 64,
            size_bytes=len(data),
        )
    )
    event = PipelineEvent(
        tenant_id="uni-c", application_id="a1", document_id="d1", step="quality-check"
    )
    response = handle(FakeHttpEvent(body=event.model_dump_json()), None)
    assert response["statusCode"] == 200
    assert json.loads(response["body"])["accepted"] is True
