import pytest

from common.errors import RecordNotFoundError
from common.repositories.reviews import InMemoryReviewRepository, ReviewOutcome, ReviewStatus


def test_open_is_idempotent_and_merges_reasons():
    repo = InMemoryReviewRepository()
    first = repo.open("uni-a", "d1", ["low_confidence"])
    again = repo.open("uni-a", "d1", ["rule:fsc-min-70", "low_confidence"])
    assert len(repo.items) == 1
    assert again.reasons == ["low_confidence", "rule:fsc-min-70"]
    assert again.created_at == first.created_at


def test_list_is_tenant_scoped_and_ordered():
    repo = InMemoryReviewRepository()
    repo.open("uni-a", "d1", ["x"])
    repo.open("uni-a", "d2", ["x"])
    repo.open("uni-b", "d3", ["x"])
    assert [i.document_id for i in repo.list("uni-a", ReviewStatus.OPEN)] == ["d1", "d2"]


def test_resolve_and_reopen():
    repo = InMemoryReviewRepository()
    repo.open("uni-a", "d1", ["x"])
    resolved = repo.resolve(
        "uni-a", "d1", "staff-1", ReviewOutcome.APPROVE, {"board": "BISE Lahore"}
    )
    assert resolved.status is ReviewStatus.RESOLVED and resolved.resolved_at is not None
    assert repo.list("uni-a", ReviewStatus.OPEN) == []
    assert repo.open("uni-a", "d1", ["y"]).status is ReviewStatus.OPEN


def test_missing_item_raises():
    with pytest.raises(RecordNotFoundError):
        InMemoryReviewRepository().get("uni-a", "nope")
