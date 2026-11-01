"""An OCR engine that returns known text for known images.

Evaluation and end-to-end tests render synthetic documents whose exact
text is known. Mapping each image's bytes to that text measures every
step after OCR independently of OCR errors.
"""

import hashlib

from common.ocr.base import OcrResult, StaticOcrEngine


class LabelOcrEngine:
    """Looks up the ground-truth text registered for an image."""

    name = "ground-truth"

    def __init__(self, confidence: float = 0.99) -> None:
        """Return registered texts with ``confidence`` per line."""
        self.confidence = confidence
        self._texts: dict[str, str] = {}

    def register(self, image: bytes, text: str) -> None:
        """Associate ``image`` with ``text``."""
        self._texts[hashlib.sha256(image).hexdigest()] = text

    def recognize(self, image: bytes) -> OcrResult:
        """Return the registered text, or nothing for unknown images."""
        text = self._texts.get(hashlib.sha256(image).hexdigest(), "")
        return StaticOcrEngine(text, self.confidence).recognize(image)
