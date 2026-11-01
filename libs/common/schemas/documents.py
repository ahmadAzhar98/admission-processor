"""Document identity, type and lifecycle status."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from common.tenant import TENANT_ID_PATTERN

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
"""A model or rule confidence in the closed interval [0, 1]."""

TenantId = Annotated[str, Field(pattern=TENANT_ID_PATTERN.pattern)]
"""A tenant slug, validated with the same rule as the request context."""

Identifier = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
"""An opaque ID that is safe to use in object keys and URLs."""


class DocumentType(StrEnum):
    """Document kinds the pipeline knows how to classify."""

    CNIC = "cnic"
    B_FORM = "b_form"
    MATRIC_RESULT = "matric_result"
    FSC_RESULT = "fsc_result"
    DOMICILE = "domicile"
    ENTRY_TEST = "entry_test"
    FEE_CHALLAN = "fee_challan"
    UNKNOWN = "unknown"


class DocumentStatus(StrEnum):
    """Lifecycle state of a document as it moves through the pipeline."""

    RECEIVED = "received"
    REUPLOAD_REQUIRED = "reupload_required"
    CLASSIFIED = "classified"
    EXTRACTED = "extracted"
    VALIDATED = "validated"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class Document(BaseModel):
    """An uploaded file and where it is stored."""

    model_config = ConfigDict(frozen=True)

    tenant_id: TenantId
    document_id: Identifier
    application_id: Identifier
    object_key: str
    content_type: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    declared_type: DocumentType | None = None
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
