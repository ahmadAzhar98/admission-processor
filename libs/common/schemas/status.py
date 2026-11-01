"""Groupings of document statuses used to coordinate application-level steps."""

from common.schemas.documents import DocumentStatus

SETTLED = frozenset(
    {
        DocumentStatus.VALIDATED,
        DocumentStatus.NEEDS_REVIEW,
        DocumentStatus.REUPLOAD_REQUIRED,
        DocumentStatus.APPROVED,
        DocumentStatus.REJECTED,
    }
)
"""Statuses in which a document's per-document processing is finished."""
