"""OCR engines behind one interface, so steps and tests can swap them."""

from common.ocr.base import OcrEngine, OcrLine, OcrResult, StaticOcrEngine

__all__ = ["OcrEngine", "OcrLine", "OcrResult", "StaticOcrEngine"]
