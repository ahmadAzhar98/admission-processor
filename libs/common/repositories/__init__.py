"""Persistence interfaces shared by the pipeline functions.

Functions depend on these protocols; tests use the in-memory versions in
:mod:`common.repositories.memory` and deployments use the PostgreSQL ones
in :mod:`common.repositories.postgres`.
"""

from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field

from common.schemas.documents import Document, DocumentStatus, DocumentType


class DocumentRecord(BaseModel):
    """A stored document with its current pipeline state."""

    document: Document
    status: DocumentStatus = DocumentStatus.RECEIVED
    document_type: DocumentType | None = None


class AuditEntry(BaseModel):
    """One state change, as written to the append-only audit log."""

    tenant_id: str
    document_id: str | None
    actor: str
    action: str
    from_status: str | None = None
    to_status: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditRepository(Protocol):
    """Append-only audit log."""

    def record(self, entry: AuditEntry) -> None:
        """Append ``entry``."""

    def list(self, tenant_id: str, document_id: str) -> list[AuditEntry]:
        """Return a document's entries, oldest first."""


class DocumentRepository(Protocol):
    """Documents and their status."""

    def add(self, document: Document) -> tuple[DocumentRecord, bool]:
        """Store ``document`` unless identical bytes exist for the application.

        Returns:
            The stored record and whether it was newly created. A duplicate
            upload returns the existing record and ``False``.
        """

    def get(self, tenant_id: str, document_id: str) -> DocumentRecord:
        """Return the record; raise RecordNotFoundError if absent."""

    def list_for_application(self, tenant_id: str, application_id: str) -> list[DocumentRecord]:
        """Return all documents of one application."""

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
        """Change status and write the matching audit entry atomically."""


class ResultRepository(Protocol):
    """Per-step results, upserted by (tenant, document, step)."""

    def save(
        self,
        tenant_id: str,
        document_id: str,
        step: str,
        result: dict[str, Any],
        confidence: float | None = None,
    ) -> None:
        """Insert or overwrite the result of ``step``."""

    def get(self, tenant_id: str, document_id: str, step: str) -> dict[str, Any] | None:
        """Return the stored result of ``step`` or ``None``."""
