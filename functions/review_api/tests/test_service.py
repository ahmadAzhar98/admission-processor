import pytest
from common.errors import InvalidRequestError
from common.repositories.reviews import ReviewStatus
from common.schemas.documents import DocumentStatus
from common.schemas.events import PipelineStep

from functions.review_api.service import Resolution, list_reviews, resolve, review_detail


def test_queue_and_detail(rt):
    [summary] = list_reviews(rt, "uni-b")
    assert summary.application_id == "a1" and summary.reasons == ["low_confidence"]
    detail = review_detail(rt, "uni-b", "d1")
    assert {f.name for f in detail.fields} == {"district", "issue_date"}
    assert list_reviews(rt, "uni-a") == []


def test_resolution_applies_corrections_and_triggers_followups(rt):
    resolution = Resolution(
        outcome="approve", reviewer="staff.1", corrections={"district": "Lahore"}
    )
    item = resolve(rt, "uni-b", "d1", resolution)
    assert item.status is ReviewStatus.RESOLVED
    stored = rt.results.get("uni-b", "d1", "extract")
    assert stored is not None
    district = next(f for f in stored["fields"] if f["name"] == "district")
    assert district == {"name": "district", "value": "Lahore", "confidence": 1.0, "source": "human"}
    assert stored["llm_used"] is True and stored["corrected_by"] == "staff.1"
    assert rt.documents.get("uni-b", "d1").status is DocumentStatus.APPROVED
    assert [e.step for e in rt.publisher.events] == [PipelineStep.FEEDBACK, PipelineStep.DECIDE]
    assert rt.audit.entries[-1].action == "review_resolved"


def test_rejection_without_corrections_skips_feedback(rt):
    resolve(rt, "uni-b", "d1", Resolution(outcome="reject", reviewer="staff.1"))
    assert rt.documents.get("uni-b", "d1").status is DocumentStatus.REJECTED
    assert [e.step for e in rt.publisher.events] == [PipelineStep.DECIDE]


@pytest.mark.parametrize("corrections", [{"unknown_field": "x"}, {"issue_date": "12/05/2025"}])
def test_invalid_corrections_are_refused(rt, corrections):
    with pytest.raises(InvalidRequestError):
        resolve(
            rt, "uni-b", "d1", Resolution(outcome="approve", reviewer="s", corrections=corrections)
        )
    assert rt.reviews.get("uni-b", "d1").status is ReviewStatus.OPEN


def test_double_resolution_is_refused(rt):
    resolve(rt, "uni-b", "d1", Resolution(outcome="approve", reviewer="s"))
    with pytest.raises(InvalidRequestError):
        resolve(rt, "uni-b", "d1", Resolution(outcome="reject", reviewer="s"))
