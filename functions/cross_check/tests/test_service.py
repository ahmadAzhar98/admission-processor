from pathlib import Path

from common.runtime import in_memory_runtime
from common.schemas.documents import Document, DocumentStatus, DocumentType
from common.schemas.events import PipelineEvent, PipelineStep
from common.schemas.results import ExtractedField, ExtractionResult

from functions.cross_check.service import process

TENANTS = Path(__file__).resolve().parents[3] / "tenants"


def _add(rt, doc_id, doc_type, status, **values):
    rt.documents.add(
        Document(
            tenant_id="uni-c",
            document_id=doc_id,
            application_id="a1",
            object_key=f"tenants/uni-c/{doc_id}",
            content_type="image/png",
            sha256=doc_id.ljust(64, "0")[:64].replace("d", "a"),
            size_bytes=1,
        )
    )
    rt.documents.set_status(
        "uni-c", doc_id, status, actor="t", document_type=DocumentType(doc_type)
    )
    extraction = ExtractionResult(
        tenant_id="uni-c",
        document_id=doc_id,
        document_type=doc_type,
        fields=[ExtractedField(name=k, value=v, confidence=0.9) for k, v in values.items()],
    )
    rt.results.save("uni-c", doc_id, "extract", extraction.model_dump(mode="json"))


EVENT = PipelineEvent(tenant_id="uni-c", application_id="a1", document_id="d1", step="cross-check")


def test_waits_until_all_documents_settle():
    rt = in_memory_runtime(TENANTS)
    _add(rt, "d1", "cnic", DocumentStatus.VALIDATED, full_name="Ali Khan")
    _add(rt, "d2", "fsc_result", DocumentStatus.EXTRACTED, full_name="Ali Khan")
    assert process(EVENT, rt) == {"waiting_for": 1}
    assert rt.publisher.events == []


def test_b_form_stands_in_for_cnic_and_mismatch_fails():
    rt = in_memory_runtime(TENANTS)
    _add(rt, "d1", "b_form", DocumentStatus.VALIDATED, full_name="Ayesha Siddiqui")
    _add(rt, "d2", "matric_result", DocumentStatus.VALIDATED, full_name="Ayesha Sidiqui")
    _add(rt, "d3", "fsc_result", DocumentStatus.VALIDATED, full_name="Hira Malik")
    summary = process(EVENT, rt)
    assert summary == {"checks": 1, "passed": False}
    stored = rt.results.get("uni-c", "d2", "cross-check")
    assert stored is not None and "between cnic and fsc_result" in stored["outcomes"][0]["message"]
    assert rt.publisher.events[0].step is PipelineStep.DECIDE


def test_documents_in_review_are_excluded_but_do_not_block():
    rt = in_memory_runtime(TENANTS)
    _add(rt, "d1", "cnic", DocumentStatus.VALIDATED, full_name="Ali Khan")
    _add(rt, "d2", "fsc_result", DocumentStatus.NEEDS_REVIEW, full_name="Someone Else")
    assert process(EVENT, rt) == {"checks": 0, "passed": True}
