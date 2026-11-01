"""Integration tests against a real PostgreSQL; run with `make test-integration`."""

import os
import uuid

import pytest

from common.schemas.documents import Document, DocumentStatus

pytestmark = pytest.mark.integration


@pytest.fixture
def db():
    from common.db.database import Database, connect_factory
    from common.db.migrate import apply_pending, discover

    dsn = os.environ.get("AP_DATABASE_URL")
    if not dsn:
        pytest.skip("AP_DATABASE_URL not set")
    database = Database(connect_factory(dsn))
    with database.transaction() as conn:
        apply_pending(conn, discover())
    yield database
    database.close()


def test_document_roundtrip_and_audit(db):
    from common.repositories.postgres import PostgresAuditRepository, PostgresDocumentRepository

    repo = PostgresDocumentRepository(db)
    doc_id = uuid.uuid4().hex
    doc = Document(
        tenant_id="uni-a",
        document_id=doc_id,
        application_id="app-it",
        object_key=f"tenants/uni-a/applications/app-it/{doc_id}",
        content_type="image/png",
        sha256=uuid.uuid4().hex * 2,
        size_bytes=1,
    )
    _, created = repo.add(doc)
    _, created_again = repo.add(doc)
    assert created and not created_again
    repo.set_status("uni-a", doc_id, DocumentStatus.CLASSIFIED, actor="test")
    assert repo.get("uni-a", doc_id).status is DocumentStatus.CLASSIFIED
    actions = [e.action for e in PostgresAuditRepository(db).list("uni-a", doc_id)]
    assert actions == ["document_received", "status_changed"]
