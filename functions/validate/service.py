"""Validate step: apply tenant rules to the stored extraction."""

import logging
from typing import Any

from common.errors import RecordNotFoundError
from common.runtime import Runtime
from common.schemas.documents import DocumentStatus
from common.schemas.events import PipelineEvent, PipelineStep
from common.schemas.results import ExtractionResult, ValidationResult

from .engine import evaluate

logger = logging.getLogger(__name__)


def process(event: PipelineEvent, rt: Runtime) -> dict[str, Any]:
    """Evaluate rules, store the outcomes, and continue to cross-check.

    Rule failures do not stop the pipeline here: the decide step weighs
    every outcome together with confidence and cross-document checks.
    """
    tid, did = event.tenant_id, event.document_id
    stored = rt.results.get(tid, did, PipelineStep.EXTRACT.value)
    if stored is None:
        raise RecordNotFoundError(f"no extraction for {did}")
    extraction = ExtractionResult.model_validate(stored)
    config = rt.tenants.get(tid)
    result = ValidationResult(outcomes=evaluate(config, extraction))
    rt.results.save(
        tid,
        did,
        PipelineStep.VALIDATE.value,
        {**result.model_dump(mode="json"), "passed": result.passed},
    )
    rt.documents.set_status(
        tid,
        did,
        DocumentStatus.VALIDATED,
        actor="validate",
        details={"failed_rules": [o.rule_id for o in result.failures]},
    )
    rt.publisher.publish(event.next(PipelineStep.CROSS_CHECK, event.payload))
    logger.info(
        "rules evaluated",
        extra={"rules": len(result.outcomes), "failed": [o.rule_id for o in result.failures]},
    )
    return {"passed": result.passed, "failed_rules": [o.rule_id for o in result.failures]}
