"""The human review queue.

A review item exists per document needing a person: low confidence,
failed rules or cross-checks, or an unrecognised type. Opening an item
twice is safe (reasons are merged), so reprocessing never duplicates
queue entries.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from common.db.database import Database
from common.errors import RecordNotFoundError


class ReviewStatus(StrEnum):
    """Whether a review item still needs attention."""

    OPEN = "open"
    RESOLVED = "resolved"


class ReviewOutcome(StrEnum):
    """The reviewer's verdict on a document."""

    APPROVE = "approve"
    REJECT = "reject"


class ReviewItem(BaseModel):
    """One document waiting for, or resolved by, a reviewer."""

    tenant_id: str
    document_id: str
    reasons: list[str]
    status: ReviewStatus = ReviewStatus.OPEN
    reviewer: str | None = None
    outcome: ReviewOutcome | None = None
    corrections: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None


class ReviewRepository(Protocol):
    """Stores review items keyed by (tenant, document)."""

    def open(self, tenant_id: str, document_id: str, reasons: list[str]) -> ReviewItem:
        """Open an item, or merge ``reasons`` into the existing one and reopen it."""

    def get(self, tenant_id: str, document_id: str) -> ReviewItem:
        """Return the item; raise RecordNotFoundError if absent."""

    def list(self, tenant_id: str, status: ReviewStatus, limit: int = 50) -> list[ReviewItem]:
        """Return items with ``status``, oldest first."""

    def resolve(
        self,
        tenant_id: str,
        document_id: str,
        reviewer: str,
        outcome: ReviewOutcome,
        corrections: dict[str, Any],
    ) -> ReviewItem:
        """Record the reviewer's verdict and corrections."""


class InMemoryReviewRepository:
    """Dictionary-backed review queue for tests."""

    def __init__(self) -> None:
        """Start with an empty queue."""
        self.items: dict[tuple[str, str], ReviewItem] = {}

    def open(self, tenant_id: str, document_id: str, reasons: list[str]) -> ReviewItem:
        """Open or reopen the item, merging reasons."""
        existing = self.items.get((tenant_id, document_id))
        merged = sorted(set(reasons) | set(existing.reasons if existing else []))
        item = ReviewItem(tenant_id=tenant_id, document_id=document_id, reasons=merged)
        if existing is not None:
            item.created_at = existing.created_at
        self.items[(tenant_id, document_id)] = item
        return item

    def get(self, tenant_id: str, document_id: str) -> ReviewItem:
        """Return the item or raise."""
        try:
            return self.items[(tenant_id, document_id)]
        except KeyError as exc:
            raise RecordNotFoundError(f"review {document_id}") from exc

    def list(self, tenant_id: str, status: ReviewStatus, limit: int = 50) -> list[ReviewItem]:
        """Return matching items, oldest first."""
        found = [i for i in self.items.values() if i.tenant_id == tenant_id and i.status == status]
        return sorted(found, key=lambda i: i.created_at)[:limit]

    def resolve(
        self,
        tenant_id: str,
        document_id: str,
        reviewer: str,
        outcome: ReviewOutcome,
        corrections: dict[str, Any],
    ) -> ReviewItem:
        """Mark the item resolved."""
        item = self.get(tenant_id, document_id).model_copy(
            update={
                "status": ReviewStatus.RESOLVED,
                "reviewer": reviewer,
                "outcome": outcome,
                "corrections": corrections,
                "resolved_at": datetime.now(UTC),
            }
        )
        self.items[(tenant_id, document_id)] = item
        return item


_COLUMNS = (
    "SELECT tenant_id, document_id, reasons, status, reviewer, outcome, corrections,"
    " created_at, resolved_at FROM review_items WHERE tenant_id = %(tenant_id)s"
)


class PostgresReviewRepository:
    """Review queue in ``review_items``."""

    def __init__(self, db: Database) -> None:
        """Use ``db`` for all statements."""
        self._db = db

    def open(self, tenant_id: str, document_id: str, reasons: list[str]) -> ReviewItem:
        """Upsert, merging reasons and reopening resolved items."""
        self._db.execute(
            "INSERT INTO review_items (tenant_id, document_id, reasons)"
            " VALUES (%(tenant_id)s, %(document_id)s, %(reasons)s)"
            " ON CONFLICT (tenant_id, document_id) DO UPDATE SET"
            " reasons = (SELECT jsonb_agg(DISTINCT r) FROM jsonb_array_elements("
            " review_items.reasons || EXCLUDED.reasons) r),"
            " status = 'open', reviewer = NULL, outcome = NULL, resolved_at = NULL",
            {"tenant_id": tenant_id, "document_id": document_id, "reasons": Jsonb(reasons)},
        )
        return self.get(tenant_id, document_id)

    def get(self, tenant_id: str, document_id: str) -> ReviewItem:
        """Return the item or raise."""
        row = self._db.fetch_one(
            _COLUMNS + " AND document_id = %(document_id)s",
            {"tenant_id": tenant_id, "document_id": document_id},
        )
        if row is None:
            raise RecordNotFoundError(f"review {document_id}")
        return ReviewItem.model_validate(row)

    def list(self, tenant_id: str, status: ReviewStatus, limit: int = 50) -> list[ReviewItem]:
        """Return matching items, oldest first."""
        rows = self._db.fetch_all(
            _COLUMNS + " AND status = %(status)s ORDER BY created_at LIMIT %(limit)s",
            {"tenant_id": tenant_id, "status": status.value, "limit": limit},
        )
        return [ReviewItem.model_validate(row) for row in rows]

    def resolve(
        self,
        tenant_id: str,
        document_id: str,
        reviewer: str,
        outcome: ReviewOutcome,
        corrections: dict[str, Any],
    ) -> ReviewItem:
        """Mark the item resolved."""
        updated = self._db.execute(
            "UPDATE review_items SET status = 'resolved', reviewer = %(reviewer)s,"
            " outcome = %(outcome)s, corrections = %(corrections)s, resolved_at = now()"
            " WHERE tenant_id = %(tenant_id)s AND document_id = %(document_id)s",
            {
                "tenant_id": tenant_id,
                "document_id": document_id,
                "reviewer": reviewer,
                "outcome": outcome.value,
                "corrections": Jsonb(corrections),
            },
        )
        if not updated:
            raise RecordNotFoundError(f"review {document_id}")
        return self.get(tenant_id, document_id)
