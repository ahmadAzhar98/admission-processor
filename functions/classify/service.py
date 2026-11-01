"""Classify step: OCR the page once, classify it, route it onward."""

import logging
from typing import Any

from common.ocr import OcrResult
from common.runtime import Runtime
from common.schemas.documents import DocumentStatus, DocumentType
from common.schemas.events import PipelineEvent, PipelineStep
from common.schemas.results import ClassificationResult

from .classifier import classify_text
from .llm_fallback import classify_with_llm

logger = logging.getLogger(__name__)

OCR_RESULT_KEY = "ocr"
"""Result key under which the OCR output is stored for the extract step."""


def ocr_payload(ocr: OcrResult) -> dict[str, Any]:
    """Serialisable form of an OCR result."""
    return {
        "engine": ocr.engine,
        "text": ocr.text,
        "mean_confidence": round(ocr.mean_confidence, 4),
        "lines": [
            {"text": ln.text, "confidence": ln.confidence, "box": list(ln.box)} for ln in ocr.lines
        ],
    }


def decide_type(
    rt: Runtime, text: str, width: int | None, height: int | None, threshold: float
) -> ClassificationResult:
    """Keyword classification, replaced by the LLM's answer when more confident."""
    result = classify_text(text, width, height)
    if result.confidence >= threshold:
        return result
    llm_result = classify_with_llm(rt.get_llm(), text)
    if llm_result is not None and llm_result.confidence > result.confidence:
        return llm_result
    return result


def process(event: PipelineEvent, rt: Runtime) -> dict[str, Any]:
    """OCR and classify the document, then send it to extract or to decide.

    Unknown types and types the tenant does not accept go straight to the
    decide step for human review; everything else is extracted, carrying
    flags for low confidence or a mismatch with the applicant's declared
    type so that decide can weigh them.
    """
    tid, did = event.tenant_id, event.document_id
    record = rt.documents.get(tid, did)
    config = rt.tenants.get(tid)
    data = rt.tenant_storage(tid).get_key(record.document.object_key)
    ocr = rt.get_ocr().recognize(data)
    rt.results.save(tid, did, OCR_RESULT_KEY, ocr_payload(ocr), ocr.mean_confidence)

    quality = rt.results.get(tid, did, PipelineStep.QUALITY_CHECK.value) or {}
    threshold = config.decision.classification_min_confidence
    result = decide_type(rt, ocr.text, quality.get("width"), quality.get("height"), threshold)
    declared = record.document.declared_type
    flags = {
        "low_confidence": result.confidence < threshold,
        "declared_mismatch": declared is not None and declared != result.document_type,
    }
    rt.results.save(
        tid,
        did,
        PipelineStep.CLASSIFY.value,
        {**result.model_dump(mode="json"), **flags},
        result.confidence,
    )

    if result.document_type is DocumentType.UNKNOWN:
        reasons = ["unrecognised_document"]
    elif result.document_type not in config.accepted_types:
        reasons = ["document_type_not_accepted"]
    else:
        reasons = []
    if reasons:
        rt.documents.set_status(
            tid, did, DocumentStatus.NEEDS_REVIEW, actor="classify", details={"reasons": reasons}
        )
        rt.publisher.publish(event.next(PipelineStep.DECIDE, {"reasons": reasons}))
    else:
        rt.documents.set_status(
            tid,
            did,
            DocumentStatus.CLASSIFIED,
            actor="classify",
            document_type=result.document_type,
        )
        rt.publisher.publish(
            event.next(PipelineStep.EXTRACT, {"document_type": result.document_type.value, **flags})
        )
    logger.info(
        "document classified",
        extra={
            "document_type": result.document_type.value,
            "confidence": result.confidence,
            "method": result.method,
        },
    )
    return {"document_type": result.document_type.value, "confidence": result.confidence}
