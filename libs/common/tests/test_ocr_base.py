import pytest

from common.ocr import OcrLine, OcrResult, StaticOcrEngine


def test_text_is_in_reading_order():
    result = OcrResult(
        engine="x",
        lines=[
            OcrLine("second", 0.9, (10, 100, 50, 120)),
            OcrLine("right", 0.9, (300, 12, 400, 30)),
            OcrLine("left", 0.9, (10, 10, 50, 30)),
        ],
    )
    assert result.text == "left\nright\nsecond"


def test_mean_confidence_is_weighted_by_length():
    result = OcrResult(engine="x", lines=[OcrLine("aaaa", 1.0), OcrLine("b", 0.0)])
    assert result.mean_confidence == pytest.approx(0.8)
    assert OcrResult(engine="x").mean_confidence == 0.0


def test_static_engine_returns_preset_text():
    engine = StaticOcrEngine("Name: Ali\nRoll No.: 1")
    result = engine.recognize(b"")
    assert result.text == "Name: Ali\nRoll No.: 1"
    assert result.engine == "static"
