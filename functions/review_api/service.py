"""Review queue operations behind the staff API.

Resolving a review stores the corrected values as human-sourced fields,
finalises the document's status, and triggers two follow-ups: the
feedback step turns the correction into a tenant few-shot example, and
the decide step re-evaluates the whole application.
"""

from datetime import date, datetime
from typing import Any

from common.errors import InvalidRequestError, RecordNotFoundError
from common.repositories import AuditEntry
from common.repositories.reviews import ReviewItem, ReviewOutcome, ReviewStatus
from common.runtime import Runtime
from common.schemas.documents import DocumentStatus, DocumentType
from common.schemas.events import PipelineEvent, PipelineStep
from common.schemas.results import (
    ExtractedField,
    ExtractionResult,
    FieldSource,
    FieldValue,
    RuleOutcome,
)
from common.tenant_config.fields import FieldSpec, FieldType
from pydantic import BaseModel, Field


class ReviewSummary(BaseModel):
    """One row of the review queue."""

    document_id: str
    application_id: str
    document_type: DocumentType | None
    reasons: list[str]
    created_at: datetime


class ReviewDetail(BaseModel):
    """Everything a reviewer needs to decide on one document."""

    item: ReviewItem
    application_id: str
    status: DocumentStatus
    document_type: DocumentType | None
    content_type: str
    fields: list[ExtractedField]
    validation: list[RuleOutcome]
    decision: dict[str, Any] | None


class Resolution(BaseModel):
    """A reviewer's verdict with optional field corrections."""

    outcome: ReviewOutcome
    reviewer: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._@-]+$")
    corrections: dict[str, FieldValue] = Field(default_factory=dict)


def list_reviews(rt: Runtime, tenant_id: str, limit: int = 50) -> list[ReviewSummary]:
    """Open review items for the tenant, oldest first."""
    summaries = []
    for item in rt.reviews.list(tenant_id, ReviewStatus.OPEN, limit):
        record = rt.documents.get(tenant_id, item.document_id)
        summaries.append(
            ReviewSummary(
                document_id=item.document_id,
                application_id=record.document.application_id,
                document_type=record.document_type,
                reasons=item.reasons,
                created_at=item.created_at,
            )
        )
    return summaries


def review_detail(rt: Runtime, tenant_id: str, document_id: str) -> ReviewDetail:
    """Item, extracted fields, rule outcomes and decision for one document."""
    item = rt.reviews.get(tenant_id, document_id)
    record = rt.documents.get(tenant_id, document_id)
    extract = rt.results.get(tenant_id, document_id, PipelineStep.EXTRACT.value) or {}
    validate = rt.results.get(tenant_id, document_id, PipelineStep.VALIDATE.value) or {}
    return ReviewDetail(
        item=item,
        application_id=record.document.application_id,
        status=record.status,
        document_type=record.document_type,
        content_type=record.document.content_type,
        fields=[ExtractedField.model_validate(f) for f in extract.get("fields", [])],
        validation=[RuleOutcome.model_validate(o) for o in validate.get("outcomes", [])],
        decision=rt.results.get(tenant_id, document_id, PipelineStep.DECIDE.value),
    )


def coerce_correction(spec: FieldSpec, value: FieldValue) -> FieldValue:
    """Check a corrected value against the field's type.

    Raises:
        InvalidRequestError: If the value does not fit the declared type.
    """
    if value is None:
        return None
    try:
        if spec.type is FieldType.INTEGER:
            return int(value)
        if spec.type is FieldType.NUMBER:
            return float(value)
        if spec.type is FieldType.DATE:
            return date.fromisoformat(str(value)).isoformat()
    except (TypeError, ValueError) as exc:
        raise InvalidRequestError(f"{spec.name} must be a {spec.type.value}") from exc
    return str(value).strip()


def apply_corrections(
    extraction: ExtractionResult, specs: dict[str, FieldSpec], corrections: dict[str, FieldValue]
) -> ExtractionResult:
    """Replace corrected fields with human-sourced values at full confidence."""
    unknown = set(corrections) - set(specs)
    if unknown:
        raise InvalidRequestError(f"unknown fields: {sorted(unknown)}")
    fields = {f.name: f for f in extraction.fields}
    for name, value in corrections.items():
        fields[name] = ExtractedField(
            name=name,
            value=coerce_correction(specs[name], value),
            confidence=1.0,
            source=FieldSource.HUMAN,
        )
    return extraction.model_copy(update={"fields": list(fields.values())})


def resolve(rt: Runtime, tenant_id: str, document_id: str, resolution: Resolution) -> ReviewItem:
    """Record the verdict, store corrections, and trigger feedback and decide.

    Raises:
        InvalidRequestError: If the item is already resolved or a correction
            is invalid.
    """
    item = rt.reviews.get(tenant_id, document_id)
    if item.status is ReviewStatus.RESOLVED:
        raise InvalidRequestError("review already resolved")
    record = rt.documents.get(tenant_id, document_id)
    config = rt.tenants.get(tenant_id)
    stored = rt.results.get(tenant_id, document_id, PipelineStep.EXTRACT.value)
    requirement = config.requirement(record.document_type) if record.document_type else None
    if resolution.corrections:
        if stored is None or requirement is None:
            raise RecordNotFoundError("no extraction to correct")
        corrected = apply_corrections(
            ExtractionResult.model_validate(stored),
            {s.name: s for s in requirement.fields},
            resolution.corrections,
        )
        rt.results.save(
            tenant_id,
            document_id,
            PipelineStep.EXTRACT.value,
            {**stored, **corrected.model_dump(mode="json"), "corrected_by": resolution.reviewer},
            corrected.confidence,
        )
    resolved = rt.reviews.resolve(
        tenant_id, document_id, resolution.reviewer, resolution.outcome, resolution.corrections
    )
    status = (
        DocumentStatus.APPROVED
        if resolution.outcome is ReviewOutcome.APPROVE
        else DocumentStatus.REJECTED
    )
    actor = f"reviewer:{resolution.reviewer}"
    rt.documents.set_status(
        tenant_id,
        document_id,
        status,
        actor=actor,
        details={"corrected_fields": sorted(resolution.corrections)},
    )
    rt.audit.record(
        AuditEntry(
            tenant_id=tenant_id,
            document_id=document_id,
            actor=actor,
            action="review_resolved",
            to_status=status.value,
            details={"outcome": resolution.outcome.value},
        )
    )
    base = PipelineEvent(
        tenant_id=tenant_id,
        application_id=record.document.application_id,
        document_id=document_id,
        step=PipelineStep.DECIDE,
    )
    if resolution.corrections:
        rt.publisher.publish(base.next(PipelineStep.FEEDBACK))
    rt.publisher.publish(base)
    return resolved
