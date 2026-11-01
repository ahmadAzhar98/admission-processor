"""Integration tests against the docker compose stack (make up).

Run with ``make test-integration``. Skipped unless AP_DATABASE_URL is set;
the S3 test additionally needs AP_S3_ENDPOINT.
"""

import contextlib
import os
import uuid

import pytest

from common.llm import FakeLlmClient
from common.schemas.documents import Document, DocumentType

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
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


@pytest.fixture
def document(db):
    from common.repositories.postgres import PostgresDocumentRepository

    doc_id = uuid.uuid4().hex[:24]
    doc = Document(
        tenant_id="uni-b",
        document_id=doc_id,
        application_id="app-it",
        object_key=f"tenants/uni-b/{doc_id}",
        content_type="image/png",
        sha256=uuid.uuid4().hex * 2,
        size_bytes=1,
    )
    PostgresDocumentRepository(db).add(doc)
    return doc


def test_results_upsert(db, document):
    from common.repositories.postgres import PostgresResultRepository

    repo = PostgresResultRepository(db)
    repo.save("uni-b", document.document_id, "extract", {"v": 1}, 0.5)
    repo.save("uni-b", document.document_id, "extract", {"v": 2}, 0.9)
    assert repo.get("uni-b", document.document_id, "extract") == {"v": 2}
    assert repo.get("uni-a", document.document_id, "extract") is None


def test_review_queue(db, document):
    from common.repositories.reviews import PostgresReviewRepository, ReviewOutcome, ReviewStatus

    repo = PostgresReviewRepository(db)
    repo.open("uni-b", document.document_id, ["low_confidence"])
    item = repo.open("uni-b", document.document_id, ["rule:x", "low_confidence"])
    assert sorted(item.reasons) == ["low_confidence", "rule:x"]
    resolved = repo.resolve("uni-b", document.document_id, "staff", ReviewOutcome.APPROVE, {"a": 1})
    assert resolved.status is ReviewStatus.RESOLVED and resolved.outcome is ReviewOutcome.APPROVE
    assert all(i.document_id != document.document_id for i in repo.list("uni-b", ReviewStatus.OPEN))


def test_examples_nearest_with_pgvector(db):
    from common.repositories.examples import FewShotExample, PostgresExampleRepository

    llm, repo = FakeLlmClient(), PostgresExampleRepository(db)
    tag = uuid.uuid4().hex[:8]
    for source, text in (("near", "Domicile District Lahore"), ("far", "Fee challan bank amount")):
        example = FewShotExample(
            tenant_id="uni-b",
            document_type=DocumentType.DOMICILE,
            source_document_id=f"{source}-{tag}",
            ocr_text=text,
            fields={"k": source},
        )
        repo.add(example, llm.embed(text))
        repo.add(example, llm.embed(text))  # upsert, no duplicate
    found = repo.nearest("uni-b", DocumentType.DOMICILE, llm.embed("Domicile District Kasur"), 50)
    ours = [e.source_document_id for e in found if e.source_document_id.endswith(tag)]
    assert ours == [f"near-{tag}", f"far-{tag}"]
    assert repo.nearest("uni-a", DocumentType.DOMICILE, llm.embed("x"), 5) == []


def test_notification_claims(db):
    from common.repositories.notifications import PostgresNotificationLog

    log, subject = PostgresNotificationLog(db), uuid.uuid4().hex
    assert log.claim("uni-b", subject, "approved", "sms", "ur")
    assert not log.claim("uni-b", subject, "approved", "sms", "ur")
    log.release("uni-b", subject, "approved")
    assert log.claim("uni-b", subject, "approved", "sms", "ur")


def test_s3_roundtrip():
    from common.settings import Settings
    from common.storage.s3 import S3ObjectStore

    if not os.environ.get("AP_S3_ENDPOINT"):
        pytest.skip("AP_S3_ENDPOINT not set")
    settings = Settings()
    store = S3ObjectStore.from_settings(settings)
    from botocore.exceptions import ClientError

    with contextlib.suppress(ClientError):  # bucket may already exist
        store._client.create_bucket(Bucket=settings.s3_bucket)
    key = f"tenants/uni-b/it/{uuid.uuid4().hex}.txt"
    store.put(key, b"hello", "text/plain")
    assert store.get(key) == b"hello"
    assert key in store.list("tenants/uni-b/it/")
    store.delete(key)
    assert not store.exists(key)
