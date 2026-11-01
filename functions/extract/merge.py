"""Combine caption-based and LLM readings into one confidence-scored result.

Two independent readings that agree are more trustworthy than either
alone; when they disagree, the more confident one is kept but marked
down, so the disagreement pushes the document towards human review.
"""

from common.schemas.results import ExtractedField, FieldValue

AGREEMENT_BONUS = 0.1
DISAGREEMENT_FACTOR = 0.7


def values_agree(a: FieldValue, b: FieldValue) -> bool:
    """Compare values ignoring case and spacing; numbers compare numerically."""
    if isinstance(a, int | float) and isinstance(b, int | float):
        return abs(float(a) - float(b)) < 1e-6
    return " ".join(str(a).split()).casefold() == " ".join(str(b).split()).casefold()


def merge(ocr: list[ExtractedField], llm: list[ExtractedField] | None) -> list[ExtractedField]:
    """Merge the two readings field by field.

    Args:
        ocr: Caption-based fields.
        llm: LLM fields, or ``None`` if the LLM was not consulted or failed.

    Returns:
        One field per name found by either reader, in first-seen order.
    """
    if not llm:
        return list(ocr)
    by_name = {f.name: f for f in llm}
    merged: list[ExtractedField] = []
    for field in ocr:
        other = by_name.pop(field.name, None)
        if other is None:
            merged.append(field)
        elif values_agree(field.value, other.value):
            boosted = min(1.0, max(field.confidence, other.confidence) + AGREEMENT_BONUS)
            merged.append(field.model_copy(update={"confidence": round(boosted, 4)}))
        else:
            winner = field if field.confidence >= other.confidence else other
            lowered = round(winner.confidence * DISAGREEMENT_FACTOR, 4)
            merged.append(winner.model_copy(update={"confidence": lowered}))
    merged.extend(by_name.values())
    return merged
