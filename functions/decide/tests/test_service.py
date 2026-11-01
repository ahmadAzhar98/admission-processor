from pathlib import Path

from common.repositories.reviews import ReviewStatus
from common.runtime import in_memory_runtime
from common.schemas.documents import Document, DocumentStatus, DocumentType
from common.schemas.events import PipelineEvent, PipelineStep

from functions.decide.service import process

TENANTS = Path(__file__).resolve().parents[3] / "tenants"
TYPES = ["cnic", "matric_result", "fsc_result", "fee_challan"]
EVENT = PipelineEvent(tenant_id="uni-c", application_id="a1", document_id="d0", step="decide")


def _application(confidences, status=DocumentStatus.VALIDATED):
    rt = in_memory_runtime(TENANTS)
    for i, (doc_type, confidence) in enumerate(zip(TYPES, confidences, strict=True)):
        doc_id = f"d{i}"
        rt.documents.add(
            Document(
                tenant_id="uni-c",
                document_id=doc_id,
                application_id="a1",
                object_key=f"tenants/uni-c/{doc_id}",
                content_type="image/png",
                sha256=str(i) * 64,
                size_bytes=1,
            )
        )
        rt.documents.set_status(
            "uni-c", doc_id, status, actor="t", document_type=DocumentType(doc_type)
        )
        rt.results.save(
            "uni-c",
            doc_id,
            "extract",
            {"fields": [{"name": "x", "value": "v", "confidence": confidence}]},
        )
        rt.results.save("uni-c", doc_id, "validate", {"outcomes": [], "passed": True})
    return rt


def test_confident_application_is_approved_and_notified():
    rt = _application([0.95] * 4)
    assert process(EVENT, rt)["outcome"] == "approved"
    assert all(r.status is DocumentStatus.APPROVED for r in rt.documents.records.values())
    [event] = rt.publisher.events
    assert event.step is PipelineStep.NOTIFY and event.payload["notification"] == "approved"
    assert rt.audit.entries[-1].action == "application_decided"


def test_uncertain_document_opens_one_review_item():
    rt = _application([0.95, 0.95, 0.5, 0.95])
    assert process(EVENT, rt)["outcome"] == "needs_review"
    [item] = rt.reviews.list("uni-c", ReviewStatus.OPEN)
    assert item.document_id == "d2" and item.reasons == ["low_confidence"]
    assert rt.documents.get("uni-c", "d2").status is DocumentStatus.NEEDS_REVIEW
    assert rt.documents.get("uni-c", "d0").status is DocumentStatus.VALIDATED


def test_redelivery_does_not_duplicate_reviews():
    rt = _application([0.95, 0.95, 0.5, 0.95])
    process(EVENT, rt)
    process(EVENT, rt)
    assert len(rt.reviews.items) == 1


def test_waits_while_documents_are_in_flight():
    rt = _application([0.95] * 4, status=DocumentStatus.EXTRACTED)
    assert process(EVENT, rt) == {"outcome": "waiting"}
    assert rt.publisher.events == []
