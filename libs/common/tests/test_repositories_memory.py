import pytest

from common.errors import RecordNotFoundError
from common.repositories.memory import (
    InMemoryDocumentRepository,
    InMemoryResultRepository,
)
from common.schemas.documents import Document, DocumentStatus, DocumentType


def _doc(document_id="doc-1", sha="a" * 64, tenant_id="uni-a"):
    return Document(
        tenant_id=tenant_id,
        document_id=document_id,
        application_id="app-1",
        object_key=f"tenants/{tenant_id}/applications/app-1/{document_id}",
        content_type="image/png",
        sha256=sha,
        size_bytes=3,
    )


def test_duplicate_upload_is_idempotent():
    repo = InMemoryDocumentRepository()
    first, created = repo.add(_doc())
    again, created_again = repo.add(_doc(document_id="doc-2"))
    assert created and not created_again
    assert again.document.document_id == first.document.document_id
    assert len(repo.records) == 1


def test_same_bytes_in_other_tenant_is_separate():
    repo = InMemoryDocumentRepository()
    repo.add(_doc())
    _, created = repo.add(_doc(tenant_id="uni-b"))
    assert created
    with pytest.raises(RecordNotFoundError):
        repo.get("uni-b", "doc-x")


def test_status_change_is_audited():
    repo = InMemoryDocumentRepository()
    repo.add(_doc())
    repo.set_status(
        "uni-a",
        "doc-1",
        DocumentStatus.CLASSIFIED,
        actor="classify",
        document_type=DocumentType.CNIC,
    )
    record = repo.get("uni-a", "doc-1")
    assert record.status is DocumentStatus.CLASSIFIED
    assert record.document_type is DocumentType.CNIC
    entries = repo.audit.list("uni-a", "doc-1")
    assert [e.action for e in entries] == ["document_received", "status_changed"]
    assert entries[-1].from_status == "received"
    assert entries[-1].to_status == "classified"


def test_results_upsert():
    repo = InMemoryResultRepository()
    repo.save("uni-a", "doc-1", "extract", {"v": 1}, 0.5)
    repo.save("uni-a", "doc-1", "extract", {"v": 2}, 0.9)
    assert repo.get("uni-a", "doc-1", "extract") == {"v": 2}
    assert len(repo.results) == 1
    assert repo.get("uni-b", "doc-1", "extract") is None
