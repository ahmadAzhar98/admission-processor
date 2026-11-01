"""Caption-based extraction from OCR lines using tenant field labels.

For each field the tenant declares, find the OCR line that starts with
one of its printed captions and read the value after it. Longer captions
are tried first so "Father Name" is never mistaken for "Name". This is
fast, needs no model, and handles most clean documents; the LLM step
fills what it misses.
"""

import re

from common.ocr import OcrLine
from common.schemas.results import ExtractedField, FieldSource
from common.tenant_config.fields import DocumentRequirement, FieldSpec

from .normalize import coerce

PARSE_PENALTY = 0.5
"""Confidence multiplier when a value was found but failed type or pattern."""


def _caption_value(line: str, caption: str) -> str | None:
    text = line.strip()
    if not text.lower().startswith(caption.lower()):
        return None
    rest = text[len(caption) :]
    if rest and rest[0].isalnum() and caption[-1].isalnum():
        return None  # caption is only a prefix of a longer word
    return rest.lstrip(" :.-\t")


def _captions(spec: FieldSpec) -> list[str]:
    return sorted({spec.name.replace("_", " "), *spec.labels}, key=len, reverse=True)


def _has_colon(line: str, caption: str) -> bool:
    rest = line.strip()[len(caption) :].lstrip(" \t")
    return rest.startswith(":")


def extract_field(
    spec: FieldSpec, lines: list[OcrLine], all_captions: list[str]
) -> ExtractedField | None:
    """Extract one field, or ``None`` if no line carries its caption.

    A line is only attributed to this field if no longer caption of another
    field also matches it. Lines where the caption is followed by a colon
    are tried first, so a heading such as "Board of Intermediate ..." does
    not shadow the "Board: BISE Lahore" line below it.
    """
    own = _captions(spec)
    ordered = sorted(
        lines,
        key=lambda ln: (
            not any(
                _has_colon(ln.text, c) for c in own if ln.text.strip().lower().startswith(c.lower())
            )
        ),
    )
    for line in ordered:
        longest = next((c for c in all_captions if _caption_value(line.text, c) is not None), None)
        if longest is None or longest not in own:
            continue
        raw = _caption_value(line.text, longest) or ""
        value = coerce(raw, spec.type)
        confidence = line.confidence
        if value is None or (spec.pattern and not re.fullmatch(spec.pattern, str(value))):
            confidence *= PARSE_PENALTY
        if value is None and not raw:
            continue
        return ExtractedField(
            name=spec.name,
            value=value if value is not None else raw,
            confidence=round(confidence, 4),
            source=FieldSource.OCR,
        )
    return None


def extract_fields(requirement: DocumentRequirement, lines: list[OcrLine]) -> list[ExtractedField]:
    """Extract every field of ``requirement`` that has a caption in ``lines``."""
    all_captions = sorted(
        {c for spec in requirement.fields for c in _captions(spec)}, key=len, reverse=True
    )
    found = (extract_field(spec, lines, all_captions) for spec in requirement.fields)
    return [f for f in found if f is not None]
