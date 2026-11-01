"""The OCR engine interface and its result type."""

from dataclasses import dataclass, field
from typing import Protocol

Box = tuple[int, int, int, int]
"""Axis-aligned bounding box ``(x0, y0, x1, y1)`` in image pixels."""


@dataclass(frozen=True)
class OcrLine:
    """One recognised line of text."""

    text: str
    confidence: float
    box: Box = (0, 0, 0, 0)


@dataclass(frozen=True)
class OcrResult:
    """All lines recognised in one image, with the engine that produced them."""

    engine: str
    lines: list[OcrLine] = field(default_factory=list)

    @property
    def text(self) -> str:
        """Lines in reading order (top to bottom, then left to right)."""
        ordered = sorted(self.lines, key=lambda ln: (ln.box[1] // 15, ln.box[0]))
        return "\n".join(ln.text for ln in ordered if ln.text.strip())

    @property
    def mean_confidence(self) -> float:
        """Character-weighted mean confidence, 0 when nothing was read."""
        weights = [len(ln.text) for ln in self.lines]
        if not sum(weights):
            return 0.0
        return sum(ln.confidence * w for ln, w in zip(self.lines, weights, strict=True)) / sum(
            weights
        )


class OcrEngine(Protocol):
    """Recognises text in an encoded image."""

    name: str

    def recognize(self, image: bytes) -> OcrResult:
        """Return the text found in ``image`` (PNG/JPEG/TIFF bytes)."""


class StaticOcrEngine:
    """Returns preset text regardless of the image.

    Used in tests, and to evaluate later steps on ground-truth text so
    their errors are measured separately from OCR errors.
    """

    name = "static"

    def __init__(self, text: str, confidence: float = 0.99) -> None:
        """Return ``text`` (one OcrLine per line) for every image."""
        self._result = OcrResult(
            engine=self.name,
            lines=[
                OcrLine(text=line, confidence=confidence, box=(0, i * 40, 100, i * 40 + 30))
                for i, line in enumerate(text.splitlines())
            ],
        )

    def recognize(self, image: bytes) -> OcrResult:
        """Return the preset result."""
        return self._result
