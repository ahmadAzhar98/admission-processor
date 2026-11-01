"""In-memory repositories for unit tests and local experiments."""

from typing import Any

from common.errors import RecordNotFoundError
from common.repositories import AuditEntry, DocumentRecord
from common.schemas.documents import Document, DocumentStatus, DocumentType


class InMemoryAuditRepository:
    """List-backed audit log."""

    def __init__(self) -> None:
        """Create an empty log."""
        self.entries: list[AuditEntry] = []

    def record(self, entry: AuditEntry) -> None:
        """Append ``entry``."""
        self.entries.append(entry)

    def list(self, tenant_id: str, document_id: str) -> list[AuditEntry]:
        """Return a document's entries, oldest first."""
        return [
            e for e in self.entries if e.tenant_id == tenant_id and e.document_id == document_id
        ]


class InMemoryDocumentRepository:
    """Dictionary-backed documents keyed by (tenant, document)."""

    def __init__(self, audit: InMemoryAuditRepository | None = None) -> None:
        """Create an empty repository writing audit entries to ``audit``."""
        self.audit = audit or InMemoryAuditRepository()
        self.records: dict[tuple[str, str], DocumentRecord] = {}

    def add(self, document: Document) -> tuple[DocumentRecord, bool]:
        """Store ``document`` unless the same bytes exist for the application."""
        for record in self.records.values():
            existing = record.document
            if (existing.tenant_id, existing.application_id, existing.sha256) == (
                document.tenant_id,
                document.application_id,
                document.sha256,
            ):
                return record, False
        record = DocumentRecord(document=document)
        self.records[(document.tenant_id, document.document_id)] = record
        self.audit.record(
            AuditEntry(
                tenant_id=document.tenant_id,
                document_id=document.document_id,
                actor="intake",
                action="document_received",
                to_status=DocumentStatus.RECEIVED,
            )
        )
        return record, True

    def get(self, tenant_id: str, document_id: str) -> DocumentRecord:
        """Return the record or raise RecordNotFoundError."""
        try:
            return self.records[(tenant_id, document_id)]
        except KeyError as exc:
            raise RecordNotFoundError(f"document {document_id}") from exc

    def list_for_application(self, tenant_id: str, application_id: str) -> list[DocumentRecord]:
        """Return all documents of one application."""
        return [
            r
            for (tid, _), r in self.records.items()
            if tid == tenant_id and r.document.application_id == application_id
        ]

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
        """Change status and record the audit entry."""
        record = self.get(tenant_id, document_id)
        updated = record.model_copy(
            update={
                "status": status,
                "document_type": document_type or record.document_type,
            }
        )
        self.records[(tenant_id, document_id)] = updated
        self.audit.record(
            AuditEntry(
                tenant_id=tenant_id,
                document_id=document_id,
                actor=actor,
                action="status_changed",
                from_status=record.status,
                to_status=status,
                details=details or {},
            )
        )


class InMemoryResultRepository:
    """Dictionary-backed step results; saving twice overwrites."""

    def __init__(self) -> None:
        """Create an empty repository."""
        self.results: dict[tuple[str, str, str], tuple[dict[str, Any], float | None]] = {}

    def save(
        self,
        tenant_id: str,
        document_id: str,
        step: str,
        result: dict[str, Any],
        confidence: float | None = None,
    ) -> None:
        """Insert or overwrite the result of ``step``."""
        self.results[(tenant_id, document_id, step)] = (result, confidence)

    def get(self, tenant_id: str, document_id: str, step: str) -> dict[str, Any] | None:
        """Return the stored result or ``None``."""
        found = self.results.get((tenant_id, document_id, step))
        return found[0] if found else None
