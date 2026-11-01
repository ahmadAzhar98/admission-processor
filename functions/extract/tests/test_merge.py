import pytest
from common.schemas.results import ExtractedField

from functions.extract.merge import merge, values_agree


def _f(name, value, confidence, source="ocr"):
    return ExtractedField(name=name, value=value, confidence=confidence, source=source)


@pytest.mark.parametrize(
    ("a", "b", "agree"),
    [("Ali  Khan", "ali khan", True), (950, 950.0, True), ("BISE Lahore", "BISE Multan", False)],
)
def test_values_agree(a, b, agree):
    assert values_agree(a, b) is agree


def test_agreement_boosts_confidence():
    [field] = merge([_f("board", "BISE Lahore", 0.8)], [_f("board", "bise lahore", 0.85, "llm")])
    assert field.confidence == pytest.approx(0.95)
    assert field.source == "ocr"


def test_disagreement_keeps_more_confident_but_lowers_it():
    [field] = merge([_f("board", "BISE Lahore", 0.6)], [_f("board", "BISE Multan", 0.9, "llm")])
    assert field.value == "BISE Multan"
    assert field.confidence == pytest.approx(0.63)


def test_fields_found_by_one_reader_are_kept():
    merged = merge([_f("a", "1", 0.9)], [_f("b", "2", 0.7, "llm")])
    assert [f.name for f in merged] == ["a", "b"]


def test_without_llm_ocr_fields_pass_through():
    fields = [_f("a", "1", 0.9)]
    assert merge(fields, None) == fields
