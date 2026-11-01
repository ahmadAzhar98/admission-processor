"""Extract step: tenant-defined fields from the stored OCR output."""

import logging
from typing import Any

from common.errors import InvalidRequestError, UpstreamServiceError
from common.ocr import OcrLine
from common.repositories.examples import FewShotExample
from common.runtime import Runtime
from common.schemas.documents import DocumentStatus, DocumentType
from common.schemas.events import PipelineEvent, PipelineStep
from common.schemas.results import ExtractedField, ExtractionResult
from common.tenant_config.fields import DocumentRequirement
from common.tenant_config.models import TenantConfig

from .heuristic import extract_fields
from .llm_extract import extract_with_llm
from .merge import merge

logger = logging.getLogger(__name__)

OCR_RESULT_KEY = "ocr"


def load_ocr(rt: Runtime, event: PipelineEvent, object_key: str) -> tuple[str, list[OcrLine]]:
    """Reuse the OCR stored by classify, or run OCR if it is missing."""
    stored = rt.results.get(event.tenant_id, event.document_id, OCR_RESULT_KEY)
    if stored is not None:
        lines = [
            OcrLine(text=ln["text"], confidence=ln["confidence"], box=tuple(ln["box"]))
            for ln in stored["lines"]
        ]
        return str(stored["text"]), lines
    data = rt.tenant_storage(event.tenant_id).get_key(object_key)
    result = rt.get_ocr().recognize(data)
    return result.text, result.lines


def needs_llm(
    fields: list[ExtractedField], requirement: DocumentRequirement, threshold: float
) -> bool:
    """Call the LLM only if a required field is missing or any is uncertain."""
    found = {f.name: f for f in fields}
    for spec in requirement.fields:
        field = found.get(spec.name)
        if (field is None and spec.required) or (field and field.confidence < threshold):
            return True
    return False


def retrieve_examples(
    rt: Runtime, config: TenantConfig, document_type: DocumentType, text: str
) -> list[FewShotExample]:
    """Nearest tenant examples for the prompt; none if embedding fails."""
    k = config.decision.few_shot_examples
    if k == 0:
        return []
    try:
        embedding = rt.get_llm().embed(text)
    except UpstreamServiceError:
        return []
    return rt.examples.nearest(config.tenant_id, document_type, embedding, k)


def extract(
    rt: Runtime,
    config: TenantConfig,
    document_type: DocumentType,
    document_id: str,
    text: str,
    lines: list[OcrLine],
) -> tuple[ExtractionResult, dict[str, Any]]:
    """Run caption extraction, then the LLM if needed, and merge the readings.

    Required fields that neither reader found are recorded with a null value
    and zero confidence, so the result's confidence forces human review.
    """
    requirement = config.requirement(document_type)
    if requirement is None:
        raise InvalidRequestError(f"{document_type} is not configured for {config.tenant_id}")
    threshold = config.decision.auto_approve_min_confidence
    ocr_fields = extract_fields(requirement, lines)
    llm_fields = None
    examples: list[FewShotExample] = []
    if needs_llm(ocr_fields, requirement, threshold):
        examples = retrieve_examples(rt, config, document_type, text)
        llm_fields = extract_with_llm(rt.get_llm(), requirement, text, examples)
    fields = merge(ocr_fields, llm_fields)
    found = {f.name for f in fields}
    fields += [
        ExtractedField(name=spec.name, value=None, confidence=0.0)
        for spec in requirement.fields
        if spec.required and spec.name not in found
    ]
    result = ExtractionResult(
        tenant_id=config.tenant_id,
        document_id=document_id,
        document_type=document_type,
        fields=fields,
    )
    meta = {"llm_used": llm_fields is not None, "examples_used": len(examples)}
    return result, meta


def process(event: PipelineEvent, rt: Runtime) -> dict[str, Any]:
    """Extract fields, store them, and hand the document to validation."""
    tid, did = event.tenant_id, event.document_id
    record = rt.documents.get(tid, did)
    config = rt.tenants.get(tid)
    document_type = record.document_type or DocumentType(event.payload["document_type"])
    text, lines = load_ocr(rt, event, record.document.object_key)
    result, meta = extract(rt, config, document_type, did, text, lines)
    rt.results.save(
        tid,
        did,
        PipelineStep.EXTRACT.value,
        {**result.model_dump(mode="json"), **meta},
        result.confidence,
    )
    rt.documents.set_status(tid, did, DocumentStatus.EXTRACTED, actor="extract")
    rt.publisher.publish(
        event.next(PipelineStep.VALIDATE, {**event.payload, "document_type": document_type.value})
    )
    logger.info(
        "fields extracted",
        extra={"fields": len(result.fields), "confidence": result.confidence, **meta},
    )
    return {"fields": len(result.fields), "confidence": result.confidence, **meta}
