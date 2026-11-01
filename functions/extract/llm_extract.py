"""Schema-driven LLM extraction with tenant few-shot examples.

The JSON schema and the Pydantic model that validates the answer are
both built from the tenant's field specs at runtime, so a new field in a
tenant config is extracted without code changes.
"""

import json
import logging
import re
from typing import Any

from common.errors import UpstreamServiceError
from common.llm import LlmClient
from common.repositories.examples import FewShotExample
from common.schemas.results import ExtractedField, FieldSource
from common.tenant_config.fields import DocumentRequirement, FieldSpec, FieldType
from pydantic import BaseModel, Field, ValidationError, create_model

from .heuristic import PARSE_PENALTY
from .normalize import coerce

logger = logging.getLogger(__name__)

MAX_TEXT_CHARS = 3000
JSON_TYPES = {
    FieldType.STRING: "string",
    FieldType.INTEGER: "integer",
    FieldType.NUMBER: "number",
    FieldType.DATE: "string",
}


class FieldAnswer(BaseModel):
    """The model's answer for one field."""

    value: str | int | float | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)


def answer_model(requirement: DocumentRequirement) -> type[BaseModel]:
    """Pydantic model with one optional :class:`FieldAnswer` per tenant field."""
    fields: dict[str, Any] = {spec.name: (FieldAnswer | None, None) for spec in requirement.fields}
    return create_model(f"Answer_{requirement.type.value}", **fields)


def response_schema(requirement: DocumentRequirement) -> dict[str, Any]:
    """JSON schema constraining the model's output to the tenant's fields."""
    properties = {
        spec.name: {
            "type": "object",
            "properties": {
                "value": {"type": [JSON_TYPES[spec.type], "null"]},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["value", "confidence"],
        }
        for spec in requirement.fields
    }
    return {"type": "object", "properties": properties, "required": list(properties)}


def _describe(spec: FieldSpec) -> str:
    hint = "date as YYYY-MM-DD" if spec.type is FieldType.DATE else spec.type.value
    captions = f"; printed as {', '.join(spec.labels)}" if spec.labels else ""
    return f"- {spec.name} ({hint}{captions}) {spec.description}".rstrip()


def build_prompt(
    requirement: DocumentRequirement, text: str, examples: list[FewShotExample]
) -> str:
    """Prompt with field descriptions, verified examples and the OCR text."""
    fields = "\n".join(_describe(spec) for spec in requirement.fields)
    shots = "".join(
        f"\nExample document:\n<<<\n{ex.ocr_text[:MAX_TEXT_CHARS]}\n>>>\n"
        f"Verified fields: {json.dumps(ex.fields, ensure_ascii=False)}\n"
        for ex in examples
    )
    return (
        f"Extract fields from a scanned {requirement.type.value.replace('_', ' ')} "
        "issued in Pakistan. The OCR text may contain errors and Urdu.\n"
        f"Fields:\n{fields}\n"
        "Use null when a field is not present. Give each value a confidence from 0 to 1.\n"
        f"{shots}\nDocument:\n<<<\n{text[:MAX_TEXT_CHARS]}\n>>>"
    )


def extract_with_llm(
    llm: LlmClient,
    requirement: DocumentRequirement,
    text: str,
    examples: list[FewShotExample],
) -> list[ExtractedField] | None:
    """Ask the LLM for every field; ``None`` if the call or validation fails."""
    try:
        raw = llm.complete_json(
            build_prompt(requirement, text, examples), response_schema(requirement)
        )
        answer = answer_model(requirement).model_validate(raw)
    except (UpstreamServiceError, ValidationError):
        logger.warning("llm extraction unavailable")
        return None
    fields = []
    for spec in requirement.fields:
        entry: FieldAnswer | None = getattr(answer, spec.name)
        if entry is None or entry.value is None:
            continue
        value = coerce(str(entry.value), spec.type)
        confidence = entry.confidence
        if value is None or (spec.pattern and not re.fullmatch(spec.pattern, str(value))):
            confidence *= PARSE_PENALTY
        fields.append(
            ExtractedField(
                name=spec.name,
                value=value if value is not None else str(entry.value),
                confidence=round(confidence, 4),
                source=FieldSource.LLM,
            )
        )
    return fields
