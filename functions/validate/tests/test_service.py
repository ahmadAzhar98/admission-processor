import json
from pathlib import Path

import pytest
from common.runtime import in_memory_runtime, set_runtime
from common.schemas.documents import Document, DocumentStatus
from common.schemas.events import PipelineEvent, PipelineStep
from common.schemas.results import ExtractedField, ExtractionResult
from common.testing import FakeHttpEvent

from functions.validate.handler import handle

TENANTS = Path(__file__).resolve().parents[3] / "tenants"


@pytest.fixture
def rt():
    runtime = in_memory_runtime(TENANTS)
    set_runtime(runtime)
    yield runtime
    set_runtime(None)


def _stage(rt, tenant_id, marks):
    rt.documents.add(
        Document(
            tenant_id=tenant_id,
            document_id="d1",
            application_id="a1",
            object_key=f"tenants/{tenant_id}/x",
            content_type="image/png",
            sha256="5" * 64,
            size_bytes=1,
        )
    )
    values = {
        "full_name": "Ali Khan",
        "father_name": "Omar Khan",
        "roll_number": "123456",
        "board": "BISE Lahore",
        "passing_year": 2025,
        "obtained_marks": marks,
        "total_marks": 1100,
    }
    extraction = ExtractionResult(
        tenant_id=tenant_id,
        document_id="d1",
        document_type="fsc_result",
        fields=[ExtractedField(name=k, value=v, confidence=0.95) for k, v in values.items()],
    )
    rt.results.save(
        tenant_id, "d1", "extract", {**extraction.model_dump(mode="json"), "llm_used": False}
    )
    event = PipelineEvent(
        tenant_id=tenant_id, application_id="a1", document_id="d1", step="validate"
    )
    return FakeHttpEvent(body=event.model_dump_json())


def test_failing_rule_is_recorded_and_pipeline_continues(rt):
    response = handle(_stage(rt, "uni-a", 700), None)
    body = json.loads(response["body"])
    assert body["passed"] is False and "fsc-min-70" in body["failed_rules"]
    assert rt.documents.get("uni-a", "d1").status is DocumentStatus.VALIDATED
    assert rt.publisher.events[0].step is PipelineStep.CROSS_CHECK


def test_same_document_passes_lenient_tenant(rt):
    body = json.loads(handle(_stage(rt, "uni-c", 700), None)["body"])
    assert body["passed"] is True


def test_missing_extraction_is_404(rt):
    event = PipelineEvent(tenant_id="uni-a", application_id="a1", document_id="zz", step="validate")
    assert handle(FakeHttpEvent(body=event.model_dump_json()), None)["statusCode"] == 404
