"""Cross-check step: compare fields across all documents of an application."""

import logging
from typing import Any

from common.repositories import DocumentRecord
from common.runtime import Runtime
from common.schemas.documents import DocumentStatus, DocumentType
from common.schemas.events import PipelineEvent, PipelineStep
from common.schemas.results import ExtractionResult
from common.schemas.status import SETTLED
from common.tenant_config.models import TenantConfig

from .matching import Observation, check

logger = logging.getLogger(__name__)


def effective_type(config: TenantConfig, document_type: DocumentType) -> DocumentType:
    """Map an alternative (B-form) to the type it stands in for (CNIC)."""
    for req in config.documents:
        if document_type in req.alternatives:
            return req.type
    return document_type


def observations(
    rt: Runtime, config: TenantConfig, records: list[DocumentRecord], field: str
) -> list[Observation]:
    """Collect ``field`` from every validated document that extracted it."""
    found = []
    for record in records:
        if record.status is not DocumentStatus.VALIDATED or record.document_type is None:
            continue
        doc_id = record.document.document_id
        stored = rt.results.get(config.tenant_id, doc_id, PipelineStep.EXTRACT.value)
        if stored is None:
            continue
        value = ExtractionResult.model_validate(stored).value(field)
        found.append(Observation(effective_type(config, record.document_type), doc_id, value))
    return found


def process(event: PipelineEvent, rt: Runtime) -> dict[str, Any]:
    """Run cross-checks once every document of the application has settled.

    Each document's validation triggers this step; all but the last see
    unsettled documents and return early, so the comparison runs once the
    full set is available. Running it again overwrites the same results.
    """
    tid = event.tenant_id
    records = rt.documents.list_for_application(tid, event.application_id)
    pending = [r for r in records if r.status not in SETTLED]
    if pending:
        return {"waiting_for": len(pending)}
    config = rt.tenants.get(tid)
    outcomes = []
    for spec in config.cross_checks:
        relevant = [
            o
            for o in observations(rt, config, records, spec.field)
            if o.document_type in spec.documents
        ]
        outcome = check(spec, relevant)
        if outcome is not None:
            outcomes.append(outcome)
    payload = {
        "outcomes": [o.model_dump(mode="json") for o in outcomes],
        "passed": all(o.passed for o in outcomes),
    }
    for record in records:
        rt.results.save(tid, record.document.document_id, PipelineStep.CROSS_CHECK.value, payload)
    rt.publisher.publish(event.next(PipelineStep.DECIDE))
    logger.info("cross-checks run", extra={"checks": len(outcomes), "passed": payload["passed"]})
    return {"checks": len(outcomes), "passed": payload["passed"]}
