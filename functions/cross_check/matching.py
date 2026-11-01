"""Compare one field across several documents of an application.

Names are compared with token-sort fuzzy matching, which tolerates OCR
slips and reordered names ("Khan Ali" vs "Ali Khan"); identifiers such
as CNIC numbers are compared exactly after removing separators.
"""

import re
from dataclasses import dataclass

from common.schemas.documents import DocumentType
from common.schemas.results import FieldValue, RuleOutcome
from common.tenant_config.models import CrossCheck
from rapidfuzz import fuzz


@dataclass(frozen=True)
class Observation:
    """A field value as read from one document."""

    document_type: DocumentType
    document_id: str
    value: FieldValue


def normalise_identifier(value: FieldValue) -> str:
    """Drop everything but letters and digits, uppercase."""
    return re.sub(r"[^0-9A-Za-z]", "", str(value)).upper()


def similarity(a: FieldValue, b: FieldValue, method: str) -> float:
    """Similarity in [0, 1]: exact identifier match or fuzzy name match."""
    if method == "exact":
        return 1.0 if normalise_identifier(a) == normalise_identifier(b) else 0.0
    return fuzz.token_sort_ratio(str(a).casefold(), str(b).casefold()) / 100.0


def check(spec: CrossCheck, observations: list[Observation]) -> RuleOutcome | None:
    """Compare every observation with the first one in ``spec.documents`` order.

    Returns ``None`` when fewer than two documents carry the field, since
    there is nothing to compare. The message names document types and the
    similarity score, never the values.
    """
    ordered = sorted(
        (o for o in observations if o.value is not None),
        key=lambda o: spec.documents.index(o.document_type),
    )
    if len(ordered) < 2:
        return None
    reference = ordered[0]
    worst = min(
        ((similarity(reference.value, o.value, spec.method), o) for o in ordered[1:]),
        key=lambda pair: pair[0],
    )
    score, other = worst
    passed = score >= spec.min_similarity
    return RuleOutcome(
        rule_id=f"crosscheck:{spec.field}",
        passed=passed,
        severity=spec.severity,
        message=(
            f"{spec.field} similarity {score:.2f} between "
            f"{reference.document_type.value} and {other.document_type.value}"
        ),
    )
