"""Decide step: gather evidence for an application and act on the policy."""

import logging
from typing import Any

from common.repositories import AuditEntry, DocumentRecord
from common.runtime import Runtime
from common.schemas.documents import DocumentStatus
from common.schemas.events import PipelineEvent, PipelineStep
from common.schemas.results import RuleOutcome
from common.schemas.status import SETTLED

from .policy import Decision, DocumentEvidence, Outcome, decide

logger = logging.getLogger(__name__)

FINAL_STATUS = {
    Outcome.APPROVED: DocumentStatus.APPROVED,
    Outcome.REJECTED: DocumentStatus.REJECTED,
}


def evidence(rt: Runtime, tenant_id: str, record: DocumentRecord) -> DocumentEvidence:
    """Assemble one document's evidence from stored step results."""
    doc_id = record.document.document_id
    extract = rt.results.get(tenant_id, doc_id, PipelineStep.EXTRACT.value) or {}
    classify = rt.results.get(tenant_id, doc_id, PipelineStep.CLASSIFY.value) or {}
    validate = rt.results.get(tenant_id, doc_id, PipelineStep.VALIDATE.value) or {}
    fields = extract.get("fields", [])
    confidence = min((float(f["confidence"]) for f in fields), default=0.0)
    failures = [
        RuleOutcome.model_validate(o) for o in validate.get("outcomes", []) if not o["passed"]
    ]
    return DocumentEvidence(
        document_id=doc_id,
        document_type=record.document_type,
        status=record.status,
        extraction_confidence=confidence,
        classification_flags={
            "low_confidence": bool(classify.get("low_confidence")),
            "declared_mismatch": bool(classify.get("declared_mismatch")),
        },
        failures=failures,
    )


def apply_decision(
    rt: Runtime, event: PipelineEvent, records: list[DocumentRecord], decision: Decision
) -> None:
    """Persist the decision, update statuses, open reviews, and audit it."""
    tid = event.tenant_id
    payload = decision.model_dump(mode="json")
    for record in records:
        doc_id = record.document.document_id
        rt.results.save(tid, doc_id, PipelineStep.DECIDE.value, payload, decision.confidence)
        target = FINAL_STATUS.get(decision.outcome)
        if decision.outcome is Outcome.NEEDS_REVIEW and doc_id in decision.review_documents:
            rt.reviews.open(tid, doc_id, decision.review_documents[doc_id])
            target = DocumentStatus.NEEDS_REVIEW
        if target is not None and target is not record.status:
            rt.documents.set_status(
                tid, doc_id, target, actor="decide", details={"reasons": decision.reasons}
            )
    rt.audit.record(
        AuditEntry(
            tenant_id=tid,
            document_id=None,
            actor="decide",
            action="application_decided",
            to_status=decision.outcome.value,
            details={"application_id": event.application_id, "reasons": decision.reasons},
        )
    )


def process(event: PipelineEvent, rt: Runtime) -> dict[str, Any]:
    """Decide the application once all its documents have settled."""
    tid = event.tenant_id
    records = rt.documents.list_for_application(tid, event.application_id)
    if any(r.status not in SETTLED for r in records):
        return {"outcome": "waiting"}
    config = rt.tenants.get(tid)
    cross = rt.results.get(tid, event.document_id, PipelineStep.CROSS_CHECK.value) or {}
    cross_checks = [RuleOutcome.model_validate(o) for o in cross.get("outcomes", [])]
    decision = decide(config, [evidence(rt, tid, r) for r in records], cross_checks)
    apply_decision(rt, event, records, decision)
    if decision.outcome is not Outcome.INCOMPLETE:
        rt.publisher.publish(
            event.next(
                PipelineStep.NOTIFY,
                {"notification": decision.outcome.value, "reasons": decision.reasons},
            )
        )
    logger.info("application decided", extra={"outcome": decision.outcome.value})
    return {"outcome": decision.outcome.value, "reasons": decision.reasons}
