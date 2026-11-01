"""LLM classification for documents the keyword rules are unsure about."""

import logging
from typing import Any

from common.errors import UpstreamServiceError
from common.llm import LlmClient
from common.schemas.documents import DocumentType
from common.schemas.results import ClassificationResult
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

MAX_TEXT_CHARS = 2000

DESCRIPTIONS = {
    DocumentType.CNIC: "Pakistani national identity card (CNIC)",
    DocumentType.B_FORM: "child registration certificate (B-form) for under-18s",
    DocumentType.MATRIC_RESULT: "Matric / SSC (grade 10) result card",
    DocumentType.FSC_RESULT: "FSc / HSSC / Intermediate (grade 12) result card",
    DocumentType.DOMICILE: "district domicile certificate",
    DocumentType.ENTRY_TEST: "university entry or admission test scorecard",
    DocumentType.FEE_CHALLAN: "paid bank fee challan / deposit slip",
    DocumentType.UNKNOWN: "none of the above",
}


class LlmAnswer(BaseModel):
    """Schema the model must answer with."""

    document_type: DocumentType
    confidence: float = Field(ge=0, le=1)


def build_prompt(text: str) -> str:
    """Prompt listing the allowed types and the (truncated) OCR text."""
    options = "\n".join(f"- {t.value}: {d}" for t, d in DESCRIPTIONS.items())
    return (
        "You classify scanned Pakistani university admission documents.\n"
        "The OCR text may contain recognition errors and Urdu.\n"
        f"Allowed document_type values:\n{options}\n\n"
        "Answer with the single best document_type and your confidence (0 to 1).\n\n"
        f"OCR text:\n<<<\n{text[:MAX_TEXT_CHARS]}\n>>>"
    )


def classify_with_llm(llm: LlmClient, text: str) -> ClassificationResult | None:
    """Ask the LLM to classify ``text``; ``None`` if it fails or answers badly.

    A failed fallback is not an error for the pipeline: the step keeps the
    keyword result and the low confidence sends the document to review.
    """
    schema: dict[str, Any] = LlmAnswer.model_json_schema()
    try:
        answer = LlmAnswer.model_validate(llm.complete_json(build_prompt(text), schema))
    except (UpstreamServiceError, ValidationError):
        logger.warning("llm classification unavailable")
        return None
    return ClassificationResult(
        document_type=answer.document_type, confidence=answer.confidence, method="llm"
    )
