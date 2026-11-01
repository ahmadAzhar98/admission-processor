"""PaddleOCR adapter (primary engine).

PaddleOCR gives better accuracy than Tesseract on photographed, skewed
and low-contrast documents and ships an Urdu recognition model. It is
heavy (PaddlePaddle runtime plus models), so it is imported lazily and
the model is loaded once per warm replica.
"""

import io
from collections.abc import Sequence
from typing import Any

import numpy as np
from PIL import Image

from common.errors import UpstreamServiceError
from common.ocr.base import Box, OcrLine, OcrResult


def _box(points: Any) -> Box:
    array = np.asarray(points, dtype=float).reshape(-1, 2)
    x0, y0 = array.min(axis=0)
    x1, y1 = array.max(axis=0)
    return int(x0), int(y0), int(x1), int(y1)


def parse_output(output: Any) -> list[OcrLine]:
    """Convert PaddleOCR output to lines, accepting both result formats.

    PaddleOCR 3 returns dict-like pages with ``rec_texts``, ``rec_scores``
    and ``rec_polys``; PaddleOCR 2 returns ``[[polygon, (text, score)], ...]``
    per page.
    """
    lines: list[OcrLine] = []
    pages: Sequence[Any] = output or []
    for page in pages:
        if page is None:
            continue
        if hasattr(page, "get") and page.get("rec_texts") is not None:
            for text, score, poly in zip(
                page["rec_texts"], page["rec_scores"], page["rec_polys"], strict=False
            ):
                lines.append(OcrLine(text=str(text), confidence=float(score), box=_box(poly)))
            continue
        for poly, (text, score) in page:
            lines.append(OcrLine(text=str(text), confidence=float(score), box=_box(poly)))
    return lines


class PaddleOcrEngine:
    """OCR via PaddleOCR, loaded on first use."""

    name = "paddleocr"

    def __init__(self, lang: str = "en", model: Any = None) -> None:
        """Use the ``lang`` recognition model; ``model`` is injected in tests."""
        self.lang = lang
        self._model = model

    def _load(self) -> Any:
        if self._model is None:
            try:
                from paddleocr import PaddleOCR
            except ImportError as exc:
                raise UpstreamServiceError("paddleocr is not installed") from exc
            self._model = PaddleOCR(
                lang=self.lang,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
        return self._model

    def recognize(self, image: bytes) -> OcrResult:
        """Run PaddleOCR on ``image``.

        Raises:
            UpstreamServiceError: If PaddleOCR is unavailable or fails.
        """
        model = self._load()
        try:
            pixels = np.asarray(Image.open(io.BytesIO(image)).convert("RGB"))
            output = model.predict(pixels) if hasattr(model, "predict") else model.ocr(pixels)
        except (OSError, RuntimeError, ValueError) as exc:
            raise UpstreamServiceError("paddleocr failed") from exc
        return OcrResult(engine=self.name, lines=parse_output(output))
