"""Primary/fallback OCR chaining and engine construction from settings."""

import logging

from common.errors import UpstreamServiceError
from common.ocr.base import OcrEngine, OcrResult
from common.ocr.paddle import PaddleOcrEngine
from common.ocr.tesseract import TesseractOcrEngine
from common.settings import Settings

logger = logging.getLogger(__name__)


class FallbackOcrEngine:
    """Use ``primary``; fall back when it fails or reads with low confidence.

    When both engines run, the result with the higher mean confidence wins,
    so the fallback can never make a good primary reading worse.
    """

    def __init__(self, primary: OcrEngine, fallback: OcrEngine, min_confidence: float) -> None:
        """Chain ``primary`` and ``fallback`` with a confidence cut-off."""
        self.primary = primary
        self.fallback = fallback
        self.min_confidence = min_confidence
        self.name = f"{primary.name}+{fallback.name}"

    def recognize(self, image: bytes) -> OcrResult:
        """Recognise ``image`` with the primary and, if needed, the fallback."""
        try:
            first = self.primary.recognize(image)
        except UpstreamServiceError:
            logger.warning("primary ocr failed", extra={"engine": self.primary.name})
            return self.fallback.recognize(image)
        if first.mean_confidence >= self.min_confidence:
            return first
        try:
            second = self.fallback.recognize(image)
        except UpstreamServiceError:
            return first
        return second if second.mean_confidence > first.mean_confidence else first


def build_ocr_engine(settings: Settings) -> OcrEngine:
    """Construct the engine named by ``settings.ocr_engine``."""
    paddle = PaddleOcrEngine(lang=settings.paddle_lang)
    tesseract = TesseractOcrEngine(lang=settings.tesseract_lang)
    if settings.ocr_engine == "paddle":
        return paddle
    if settings.ocr_engine == "tesseract":
        return tesseract
    return FallbackOcrEngine(paddle, tesseract, settings.ocr_min_confidence)
