import json
from pathlib import Path

import pytest
from common.ocr import StaticOcrEngine
from common.runtime import in_memory_runtime, set_runtime
from common.schemas.documents import Document
from common.schemas.events import PipelineEvent
from common.testing import FakeHttpEvent

from functions.classify.handler import handle

TENANTS = Path(__file__).resolve().parents[3] / "tenants"


@pytest.fixture
def rt():
    runtime = in_memory_runtime(TENANTS)
    runtime.ocr = StaticOcrEngine("Bank A\nFee Challan - Paid\nChallan No.: 123")
    set_runtime(runtime)
    yield runtime
    set_runtime(None)


def test_handler_classifies_queued_document(rt):
    key = rt.tenant_storage("uni-c").put(("applications", "a1", "d1.png"), b"x", "image/png")
    rt.documents.add(
        Document(
            tenant_id="uni-c",
            document_id="d1",
            application_id="a1",
            object_key=key,
            content_type="image/png",
            sha256="3" * 64,
            size_bytes=1,
        )
    )
    event = PipelineEvent(tenant_id="uni-c", application_id="a1", document_id="d1", step="classify")
    response = handle(FakeHttpEvent(body=event.model_dump_json()), None)
    assert response["statusCode"] == 200
    assert json.loads(response["body"])["document_type"] == "fee_challan"


def test_unknown_document_is_404(rt):
    event = PipelineEvent(
        tenant_id="uni-c", application_id="a1", document_id="nope", step="classify"
    )
    assert handle(FakeHttpEvent(body=event.model_dump_json()), None)["statusCode"] == 404
