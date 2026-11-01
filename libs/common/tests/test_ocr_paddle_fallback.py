import io

import pytest
from PIL import Image

from common.errors import UpstreamServiceError
from common.ocr import OcrResult, StaticOcrEngine
from common.ocr.fallback import FallbackOcrEngine, build_ocr_engine
from common.ocr.paddle import PaddleOcrEngine, parse_output
from common.settings import Settings

POLY = [[10, 10], [110, 10], [110, 30], [10, 30]]


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_parse_paddle3_output():
    page = {"rec_texts": ["Name: Ali"], "rec_scores": [0.97], "rec_polys": [POLY]}
    [line] = parse_output([page])
    assert line.text == "Name: Ali"
    assert line.box == (10, 10, 110, 30)


def test_parse_paddle2_output():
    [line] = parse_output([[[POLY, ("Roll No. 1", 0.8)]], None])
    assert line.text == "Roll No. 1" and line.confidence == 0.8


def test_engine_uses_predict_when_available():
    class Model:
        def predict(self, pixels):
            assert pixels.shape == (20, 20, 3)
            return [{"rec_texts": ["x"], "rec_scores": [0.9], "rec_polys": [POLY]}]

    assert PaddleOcrEngine(model=Model()).recognize(_png()).text == "x"


class Failing:
    name = "failing"

    def recognize(self, image):
        raise UpstreamServiceError("down")


def test_fallback_on_failure():
    engine = FallbackOcrEngine(Failing(), StaticOcrEngine("from fallback"), 0.6)
    assert engine.recognize(b"").text == "from fallback"


def test_low_confidence_picks_better_reading():
    weak = StaticOcrEngine("weak", confidence=0.3)
    strong = StaticOcrEngine("strong", confidence=0.9)
    assert FallbackOcrEngine(weak, strong, 0.6).recognize(b"").text == "strong"
    assert FallbackOcrEngine(strong, weak, 0.6).recognize(b"").text == "strong"


def test_weak_primary_kept_if_fallback_worse_or_failing():
    weak = StaticOcrEngine("weak", confidence=0.4)
    worse = StaticOcrEngine("worse", confidence=0.2)
    assert FallbackOcrEngine(weak, worse, 0.6).recognize(b"").text == "weak"
    assert FallbackOcrEngine(weak, Failing(), 0.6).recognize(b"").text == "weak"


@pytest.mark.parametrize(
    ("choice", "name"),
    [
        ("paddle", "paddleocr"),
        ("tesseract", "tesseract"),
        ("paddle+tesseract", "paddleocr+tesseract"),
    ],
)
def test_factory(choice, name):
    assert build_ocr_engine(Settings(ocr_engine=choice)).name == name


def test_result_type():
    assert isinstance(StaticOcrEngine("a").recognize(b""), OcrResult)
