"""Rule-based document classification from OCR text and page shape.

Scores every type by weighted keyword cues and a layout cue, then turns
the scores into probabilities with a softmax. The top probability is the
confidence; when it is below the tenant's threshold the caller falls
back to the LLM. Cheap, explainable rules handle the common case and the
LLM only sees the hard documents.
"""

import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from common.schemas.documents import DocumentType
from common.schemas.results import ClassificationResult

KEYWORDS_FILE = Path(__file__).parent / "keywords.yaml"
WEIGHTS = {"strong": 3.0, "weak": 1.0, "negative": -3.0, "layout": 1.0}
TEMPERATURE = 1.0


@dataclass(frozen=True)
class TypeCues:
    """Keyword and layout cues for one document type."""

    strong: tuple[str, ...]
    weak: tuple[str, ...]
    negative: tuple[str, ...]
    layout: str


@lru_cache(maxsize=1)
def load_cues(path: Path = KEYWORDS_FILE) -> dict[DocumentType, TypeCues]:
    """Read cues from ``keywords.yaml`` (cached)."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        DocumentType(name): TypeCues(
            strong=tuple(entry.get("strong", [])),
            weak=tuple(entry.get("weak", [])),
            negative=tuple(entry.get("negative", [])),
            layout=str(entry.get("layout", "")),
        )
        for name, entry in raw.items()
    }


def normalise_text(text: str) -> str:
    """Lowercase and collapse whitespace."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def page_shape(width: int, height: int) -> str:
    """Return ``card`` for landscape pages and ``portrait`` otherwise."""
    return "card" if width > height else "portrait"


def score(text: str, shape: str | None, cues: TypeCues) -> float:
    """Weighted cue score of ``text`` for one type."""
    total = 0.0
    for kind in ("strong", "weak", "negative"):
        phrases: tuple[str, ...] = getattr(cues, kind)
        total += WEIGHTS[kind] * sum(1 for phrase in phrases if phrase in text)
    if shape is not None and shape == cues.layout:
        total += WEIGHTS["layout"]
    return total


def classify_text(
    text: str, width: int | None = None, height: int | None = None
) -> ClassificationResult:
    """Classify OCR ``text``, optionally using page dimensions.

    Text with no cues at all is ``unknown`` with zero confidence rather than
    a coin flip between types.
    """
    normalised = normalise_text(text)
    shape = page_shape(width, height) if width and height else None
    scores = {doc_type: score(normalised, shape, c) for doc_type, c in load_cues().items()}
    best = max(scores, key=lambda t: scores[t])
    if scores[best] <= WEIGHTS["layout"]:
        return ClassificationResult(
            document_type=DocumentType.UNKNOWN, confidence=0.0, method="keywords"
        )
    top = max(scores.values())
    exp = {t: math.exp((s - top) / TEMPERATURE) for t, s in scores.items()}
    confidence = exp[best] / sum(exp.values())
    return ClassificationResult(
        document_type=best, confidence=round(confidence, 4), method="keywords"
    )
