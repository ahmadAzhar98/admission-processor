"""PostgreSQL implementations of the repository protocols.

All statements go through :class:`~common.db.database.Database`, which
rejects any query that does not filter on ``tenant_id``.
"""

from typing import Any

from psycopg.types.json import Jsonb

from common.db.database import Database, Row, check_tenant_scoped
from common.errors import RecordNotFoundError
from common.repositories import AuditEntry, DocumentRecord
from common.schemas.documents import Document, DocumentStatus, DocumentType

_INSERT_AUDIT = """
    INSERT INTO audit_log (tenant_id, document_id, actor, action, from_status, to_status, details)
    VALUES (%(tenant_id)s, %(document_id)s, %(actor)s, %(action)s,
            %(from_status)s, %(to_status)s, %(details)s)
"""

_SELECT_DOCUMENTS = (
    "SELECT tenant_id, document_id, application_id, object_key, content_type, sha256,"
    " size_bytes, declared_type, created_at AS uploaded_at, status, document_type"
    " FROM documents WHERE tenant_id = %(tenant_id)s"
)


def _audit_params(entry: AuditEntry) -> dict[str, Any]:
    params = entry.model_dump(exclude={"created_at"})
    params["details"] = Jsonb(entry.details)
    return params


def _to_record(row: Row) -> DocumentRecord:
    return DocumentRecord(
        document=Document.model_validate(row),
        status=DocumentStatus(row["status"]),
        document_type=DocumentType(row["document_type"]) if row["document_type"] else None,
    )


class PostgresAuditRepository:
    """Audit log stored in ``audit_log``."""

    def __init__(self, db: Database) -> None:
        """Use ``db`` for all statements."""
        self._db = db

    def record(self, entry: AuditEntry) -> None:
        """Append ``entry``."""
        self._db.execute(_INSERT_AUDIT, _audit_params(entry))

    def list(self, tenant_id: str, document_id: str) -> list[AuditEntry]:
        """Return a document's entries, oldest first."""
        rows = self._db.fetch_all(
            "SELECT tenant_id, document_id, actor, action, from_status, to_status, details,"
            " created_at FROM audit_log WHERE tenant_id = %(tenant_id)s"
            " AND document_id = %(document_id)s ORDER BY created_at, id",
            {"tenant_id": tenant_id, "document_id": document_id},
        )
        return [AuditEntry.model_validate(row) for row in rows]


class PostgresDocumentRepository:
    """Documents stored in ``documents``; status changes are audited."""

    def __init__(self, db: Database) -> None:
        """Use ``db`` for all statements."""
        self._db = db

    def add(self, document: Document) -> tuple[DocumentRecord, bool]:
        """Insert unless the same bytes already exist for the application."""
        params = document.model_dump()
        inserted = self._db.execute(
            "INSERT INTO documents (tenant_id, document_id, application_id, object_key,"
            " content_type, sha256, size_bytes, declared_type, created_at)"
            " VALUES (%(tenant_id)s, %(document_id)s, %(application_id)s, %(object_key)s,"
            " %(content_type)s, %(sha256)s, %(size_bytes)s, %(declared_type)s, %(uploaded_at)s)"
            " ON CONFLICT DO NOTHING",
            params,
        )
        if inserted:
            PostgresAuditRepository(self._db).record(
                AuditEntry(
                    tenant_id=document.tenant_id,
                    document_id=document.document_id,
                    actor="intake",
                    action="document_received",
                    to_status=DocumentStatus.RECEIVED,
                )
            )
            return self.get(document.tenant_id, document.document_id), True
        row = self._db.fetch_one(
            _SELECT_DOCUMENTS + " AND application_id = %(application_id)s AND sha256 = %(sha256)s",
            params,
        )
        if row is None:
            raise RecordNotFoundError("document conflict without matching row")
        return _to_record(row), False

    def get(self, tenant_id: str, document_id: str) -> DocumentRecord:
        """Return the record or raise RecordNotFoundError."""
        row = self._db.fetch_one(
            _SELECT_DOCUMENTS + " AND document_id = %(document_id)s",
            {"tenant_id": tenant_id, "document_id": document_id},
        )
        if row is None:
            raise RecordNotFoundError(f"document {document_id}")
        return _to_record(row)

    def list_for_application(self, tenant_id: str, application_id: str) -> list[DocumentRecord]:
        """Return all documents of one application."""
        rows = self._db.fetch_all(
            _SELECT_DOCUMENTS + " AND application_id = %(application_id)s ORDER BY created_at",
            {"tenant_id": tenant_id, "application_id": application_id},
        )
        return [_to_record(row) for row in rows]

    def set_status(
        self,
        tenant_id: str,
        document_id: str,
        status: DocumentStatus,
        *,
        actor: str,
        document_type: DocumentType | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Update status and write the audit entry in one transaction."""
        params: dict[str, Any] = {
            "tenant_id": tenant_id,
            "document_id": document_id,
            "status": status.value,
            "document_type": document_type.value if document_type else None,
        }
        update = (
            "WITH old AS (SELECT status FROM documents WHERE tenant_id = %(tenant_id)s"
            " AND document_id = %(document_id)s FOR UPDATE)"
            " UPDATE documents d SET status = %(status)s,"
            " document_type = COALESCE(%(document_type)s, d.document_type), updated_at = now()"
            " FROM old WHERE d.tenant_id = %(tenant_id)s AND d.document_id = %(document_id)s"
            " RETURNING old.status AS from_status"
        )
        check_tenant_scoped(update, params)
        with self._db.transaction() as conn, conn.cursor() as cur:
            cur.execute(update, params)
            row = cur.fetchone()
            if row is None:
                raise RecordNotFoundError(f"document {document_id}")
            entry = AuditEntry(
                tenant_id=tenant_id,
                document_id=document_id,
                actor=actor,
                action="status_changed",
                from_status=row["from_status"],
                to_status=status,
                details=details or {},
            )
            cur.execute(_INSERT_AUDIT, _audit_params(entry))


class PostgresResultRepository:
    """Step results stored in ``step_results``."""

    def __init__(self, db: Database) -> None:
        """Use ``db`` for all statements."""
        self._db = db

    def save(
        self,
        tenant_id: str,
        document_id: str,
        step: str,
        result: dict[str, Any],
        confidence: float | None = None,
    ) -> None:
        """Insert or overwrite the result of ``step``."""
        self._db.execute(
            "INSERT INTO step_results (tenant_id, document_id, step, result, confidence)"
            " VALUES (%(tenant_id)s, %(document_id)s, %(step)s, %(result)s, %(confidence)s)"
            " ON CONFLICT (tenant_id, document_id, step) DO UPDATE"
            " SET result = EXCLUDED.result, confidence = EXCLUDED.confidence, updated_at = now()",
            {
                "tenant_id": tenant_id,
                "document_id": document_id,
                "step": step,
                "result": Jsonb(result),
                "confidence": confidence,
            },
        )

    def get(self, tenant_id: str, document_id: str, step: str) -> dict[str, Any] | None:
        """Return the stored result or ``None``."""
        row = self._db.fetch_one(
            "SELECT result FROM step_results WHERE tenant_id = %(tenant_id)s"
            " AND document_id = %(document_id)s AND step = %(step)s",
            {"tenant_id": tenant_id, "document_id": document_id, "step": step},
        )
        return dict(row["result"]) if row else None
