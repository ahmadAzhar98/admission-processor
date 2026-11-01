import io
import shutil
from typing import Any

import pytest
from PIL import Image, ImageDraw

from common.ocr.tesseract import TesseractOcrEngine, lines_from_data

DATA: dict[str, list[Any]] = {
    "text": ["", "Name:", "Ali", "Khan", "Roll", "No.", "12345"],
    "conf": [-1, 95, 90, 85, 80, 70, 60],
    "block_num": [1, 1, 1, 1, 1, 1, 1],
    "par_num": [1, 1, 1, 1, 1, 1, 1],
    "line_num": [0, 1, 1, 1, 2, 2, 2],
    "left": [0, 10, 80, 130, 10, 70, 120],
    "top": [0, 10, 10, 10, 50, 50, 50],
    "width": [0, 60, 40, 50, 50, 40, 60],
    "height": [0, 20, 20, 20, 20, 20, 20],
}


def test_words_are_grouped_into_lines():
    lines = lines_from_data(DATA)
    assert [ln.text for ln in lines] == ["Name: Ali Khan", "Roll No. 12345"]
    assert lines[0].box == (10, 10, 180, 30)
    assert lines[0].confidence == pytest.approx(0.9)


class FakeBackend:
    class Output:
        DICT = "dict"

    def image_to_data(self, image, lang, config, output_type):
        assert lang == "eng+urd"
        return DATA


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_engine_uses_backend():
    result = TesseractOcrEngine("eng+urd", backend=FakeBackend()).recognize(_png())
    assert result.engine == "tesseract"
    assert "Roll No. 12345" in result.text


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract not installed")
def test_real_tesseract_reads_printed_text():
    image = Image.new("RGB", (900, 120), "white")
    ImageDraw.Draw(image).text((20, 30), "Roll No 482913", fill="black", font_size=48)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    result = TesseractOcrEngine("eng").recognize(buffer.getvalue())
    assert "482913" in result.text
