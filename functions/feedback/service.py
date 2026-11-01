"""Store a reviewed document as a few-shot example for its tenant.

The example pairs the document's OCR text with the final, human-checked
field values. Future extractions of the same tenant and document type
retrieve the most similar examples, so corrections teach the system that
university's documents without retraining any model.
"""

import logging
from typing import Any

from common.errors import RecordNotFoundError
from common.repositories import AuditEntry
from common.repositories.examples import FewShotExample
from common.runtime import Runtime
from common.schemas.events import PipelineEvent, PipelineStep

logger = logging.getLogger(__name__)

OCR_RESULT_KEY = "ocr"


def build_example(rt: Runtime, event: PipelineEvent) -> FewShotExample:
    """Assemble the example from the stored OCR text and corrected fields.

    Raises:
        RecordNotFoundError: If the document has no OCR text or extraction.
    """
    tid, did = event.tenant_id, event.document_id
    record = rt.documents.get(tid, did)
    ocr = rt.results.get(tid, did, OCR_RESULT_KEY)
    extract = rt.results.get(tid, did, PipelineStep.EXTRACT.value)
    if ocr is None or extract is None or record.document_type is None:
        raise RecordNotFoundError(f"nothing to learn from for {did}")
    fields = {f["name"]: f["value"] for f in extract["fields"] if f["value"] is not None}
    return FewShotExample(
        tenant_id=tid,
        document_type=record.document_type,
        source_document_id=did,
        ocr_text=str(ocr["text"]),
        fields=fields,
    )


def process(event: PipelineEvent, rt: Runtime) -> dict[str, Any]:
    """Embed and store the example; an embedding failure is retried by the queue."""
    example = build_example(rt, event)
    rt.examples.add(example, rt.get_llm().embed(example.ocr_text))
    rt.audit.record(
        AuditEntry(
            tenant_id=event.tenant_id,
            document_id=event.document_id,
            actor="feedback",
            action="example_stored",
            details={"document_type": example.document_type.value, "fields": len(example.fields)},
        )
    )
    logger.info("few-shot example stored", extra={"document_type": example.document_type.value})
    return {"stored": True, "fields": len(example.fields)}
