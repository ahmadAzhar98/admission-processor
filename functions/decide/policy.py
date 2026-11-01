"""The decision policy, as a pure function of the collected evidence.

An application is:

* **incomplete** while a required document is missing or must be re-uploaded;
* **rejected** when a reject-severity rule fails on a confidently read value
  (a misread value is never grounds for rejection, only for review);
* **needs review** when anything is uncertain: low extraction confidence,
  an uncertain or mismatched classification, a review-severity rule or
  cross-check failure, or a document the classifier could not place;
* **approved** otherwise.

A reviewer's verdict on a document is final: an approved document adds no
further review reasons (including cross-check failures it is part of),
and a rejected one rejects the application.

Thresholds and severities come from the tenant config, so the same
evidence can lead to different outcomes for different universities.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from common.schemas.documents import DocumentStatus, DocumentType
from common.schemas.results import RuleOutcome
from common.tenant_config.models import TenantConfig
from common.tenant_config.rules import Severity
from pydantic import BaseModel, Field


class Outcome(StrEnum):
    """Application-level decision."""

    APPROVED = "approved"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True)
class DocumentEvidence:
    """Everything earlier steps concluded about one document."""

    document_id: str
    document_type: DocumentType | None
    status: DocumentStatus
    extraction_confidence: float = 0.0
    classification_flags: dict[str, bool] = field(default_factory=dict)
    failures: list[RuleOutcome] = field(default_factory=list)


class Decision(BaseModel):
    """The outcome, why, and which documents a reviewer must look at."""

    outcome: Outcome
    reasons: list[str] = Field(default_factory=list)
    review_documents: dict[str, list[str]] = Field(default_factory=dict)
    confidence: float = 0.0


def missing_documents(config: TenantConfig, present: set[DocumentType]) -> list[str]:
    """Required document types with neither the type nor an alternative present."""
    return [
        f"missing:{req.type.value}"
        for req in config.documents
        if req.required and req.type not in present and not present & set(req.alternatives)
    ]


def _document_reasons(doc: DocumentEvidence, threshold: float) -> tuple[list[str], list[str]]:
    review: list[str] = []
    reject: list[str] = []
    if doc.status is DocumentStatus.APPROVED:
        return review, reject
    if doc.status is DocumentStatus.REJECTED:
        return review, ["reviewer_rejected"]
    if doc.status is DocumentStatus.NEEDS_REVIEW:
        review.append("unclassified_or_not_accepted")
        return review, reject
    confident = doc.extraction_confidence >= threshold
    if not confident:
        review.append("low_confidence")
    if doc.classification_flags.get("low_confidence"):
        review.append("classification_uncertain")
    if doc.classification_flags.get("declared_mismatch"):
        review.append("declared_type_mismatch")
    for failure in doc.failures:
        if failure.severity == Severity.REJECT and confident:
            reject.append(f"rule:{failure.rule_id}")
        else:
            review.append(f"rule:{failure.rule_id}")
    return review, reject


def decide(
    config: TenantConfig, documents: list[DocumentEvidence], cross_checks: list[RuleOutcome]
) -> Decision:
    """Apply the policy to an application's evidence."""
    present = {d.document_type for d in documents if d.document_type is not None}
    waiting = missing_documents(config, present) + [
        f"reupload:{d.document_id}"
        for d in documents
        if d.status is DocumentStatus.REUPLOAD_REQUIRED
    ]
    if waiting:
        return Decision(outcome=Outcome.INCOMPLETE, reasons=waiting)

    threshold = config.decision.auto_approve_min_confidence
    review_docs: dict[str, list[str]] = {}
    rejects: list[str] = []
    for doc in documents:
        review, reject = _document_reasons(doc, threshold)
        rejects += reject
        if review:
            review_docs[doc.document_id] = review

    def trusted(doc: DocumentEvidence) -> bool:
        return doc.status is DocumentStatus.APPROVED or doc.extraction_confidence >= threshold

    all_confident = all(trusted(d) for d in documents)
    specs = {f"crosscheck:{c.field}": c for c in config.cross_checks}
    for check in (c for c in cross_checks if not c.passed):
        if check.severity == Severity.REJECT and all_confident:
            rejects.append(check.rule_id)
            continue
        spec = specs.get(check.rule_id)
        for doc in documents:
            if doc.status is DocumentStatus.APPROVED:
                continue
            if spec is None or doc.document_type in spec.documents:
                review_docs.setdefault(doc.document_id, []).append(check.rule_id)

    confidence = min((d.extraction_confidence for d in documents), default=0.0)
    if rejects:
        return Decision(
            outcome=Outcome.REJECTED, reasons=sorted(set(rejects)), confidence=confidence
        )
    if review_docs:
        reasons = sorted({r for rs in review_docs.values() for r in rs})
        return Decision(
            outcome=Outcome.NEEDS_REVIEW,
            reasons=reasons,
            review_documents=review_docs,
            confidence=confidence,
        )
    return Decision(outcome=Outcome.APPROVED, confidence=confidence)
