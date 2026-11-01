"""Tesseract OCR adapter (fallback engine).

Requires the ``tesseract`` binary and the ``pytesseract`` wrapper. Urdu
needs the ``urd`` traineddata; the language string is configurable.
"""

import io
from typing import Any

from PIL import Image

from common.errors import UpstreamServiceError
from common.ocr.base import OcrLine, OcrResult


def lines_from_data(data: dict[str, list[Any]]) -> list[OcrLine]:
    """Group Tesseract word-level ``image_to_data`` output into lines.

    Words with confidence -1 (layout markers) or empty text are skipped.
    A line's confidence is the mean of its words, scaled to [0, 1].
    """
    grouped: dict[tuple[int, int, int], list[int]] = {}
    for i, word in enumerate(data["text"]):
        if not str(word).strip() or float(data["conf"][i]) < 0:
            continue
        key = (int(data["block_num"][i]), int(data["par_num"][i]), int(data["line_num"][i]))
        grouped.setdefault(key, []).append(i)
    lines = []
    for indices in grouped.values():
        x0 = min(int(data["left"][i]) for i in indices)
        y0 = min(int(data["top"][i]) for i in indices)
        x1 = max(int(data["left"][i]) + int(data["width"][i]) for i in indices)
        y1 = max(int(data["top"][i]) + int(data["height"][i]) for i in indices)
        text = " ".join(str(data["text"][i]).strip() for i in indices)
        confidence = sum(float(data["conf"][i]) for i in indices) / len(indices) / 100.0
        lines.append(OcrLine(text=text, confidence=round(confidence, 4), box=(x0, y0, x1, y1)))
    return lines


class TesseractOcrEngine:
    """OCR via the Tesseract command-line engine."""

    name = "tesseract"

    def __init__(self, lang: str = "eng", backend: Any = None) -> None:
        """Use ``lang`` (e.g. ``eng+urd``); ``backend`` replaces pytesseract in tests."""
        self.lang = lang
        self._backend = backend

    def _pytesseract(self) -> Any:
        if self._backend is None:
            try:
                import pytesseract
            except ImportError as exc:
                raise UpstreamServiceError("pytesseract is not installed") from exc
            self._backend = pytesseract
        return self._backend

    def recognize(self, image: bytes) -> OcrResult:
        """Run Tesseract on ``image`` and return line-level results.

        Raises:
            UpstreamServiceError: If Tesseract is missing or fails.
        """
        backend = self._pytesseract()
        try:
            picture = Image.open(io.BytesIO(image))
            data = backend.image_to_data(
                picture, lang=self.lang, config="--psm 3", output_type=backend.Output.DICT
            )
        except (OSError, RuntimeError) as exc:
            raise UpstreamServiceError("tesseract failed") from exc
        return OcrResult(engine=self.name, lines=lines_from_data(data))
