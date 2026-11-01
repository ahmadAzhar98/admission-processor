from pathlib import Path

import pytest
from common.errors import RecordNotFoundError
from common.llm import FakeLlmClient
from common.runtime import in_memory_runtime
from common.schemas.documents import Document, DocumentStatus, DocumentType
from common.schemas.events import PipelineEvent

from functions.feedback.service import process

TENANTS = Path(__file__).resolve().parents[3] / "tenants"
EVENT = PipelineEvent(tenant_id="uni-b", application_id="a1", document_id="d1", step="feedback")


def _runtime(with_ocr=True):
    rt = in_memory_runtime(TENANTS)
    rt.llm = FakeLlmClient()
    rt.documents.add(
        Document(
            tenant_id="uni-b",
            document_id="d1",
            application_id="a1",
            object_key="tenants/uni-b/x",
            content_type="image/png",
            sha256="7" * 64,
            size_bytes=1,
        )
    )
    rt.documents.set_status(
        "uni-b", "d1", DocumentStatus.APPROVED, actor="t", document_type=DocumentType.DOMICILE
    )
    if with_ocr:
        rt.results.save("uni-b", "d1", "ocr", {"text": "District: Lahor", "lines": []})
    rt.results.save(
        "uni-b",
        "d1",
        "extract",
        {
            "fields": [
                {"name": "district", "value": "Lahore", "confidence": 1.0, "source": "human"},
                {"name": "issue_date", "value": None, "confidence": 0.0, "source": "ocr"},
            ]
        },
    )
    return rt


def test_correction_becomes_retrievable_example():
    rt = _runtime()
    assert process(EVENT, rt) == {"stored": True, "fields": 1}
    found = rt.examples.nearest(
        "uni-b", DocumentType.DOMICILE, rt.get_llm().embed("District: Lahor"), 3
    )
    assert found[0].fields == {"district": "Lahore"}
    assert rt.audit.entries[-1].action == "example_stored"


def test_reprocessing_does_not_duplicate_examples():
    rt = _runtime()
    process(EVENT, rt)
    process(EVENT, rt)
    assert len(rt.examples.items) == 1


def test_example_is_invisible_to_other_tenants():
    rt = _runtime()
    process(EVENT, rt)
    assert rt.examples.nearest("uni-a", DocumentType.DOMICILE, [1.0] * 768, 3) == []


def test_missing_ocr_is_an_error():
    with pytest.raises(RecordNotFoundError):
        process(EVENT, _runtime(with_ocr=False))
