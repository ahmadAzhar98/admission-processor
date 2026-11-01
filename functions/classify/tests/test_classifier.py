from collections import Counter
from pathlib import Path

import pytest
from common.schemas.documents import DocumentType
from common.tenant_config.loader import TenantRegistry

from functions.classify.classifier import classify_text, load_cues, page_shape
from synthetic.generate import generate

REGISTRY = TenantRegistry(Path(__file__).resolve().parents[3] / "tenants")


def test_every_known_type_has_cues():
    assert set(load_cues()) == set(DocumentType) - {DocumentType.UNKNOWN}


def test_page_shape():
    assert page_shape(1400, 880) == "card"
    assert page_shape(1240, 1754) == "portrait"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ISLAMIC REPUBLIC OF PAKISTAN\nNational Identity Card\nIdentity Number: x", "cnic"),
        ("Higher Secondary School Certificate Examination 2025\nGroup: ICS", "fsc_result"),
        ("Secondary School Certificate Examination 2023\nRoll No.: 1", "matric_result"),
        ("Office of the District Officer\nڈومیسائل سرٹیفکیٹ", "domicile"),
        ("Bank A\nFee Challan - Paid\nChallan No.: 1", "fee_challan"),
    ],
)
def test_clear_documents(text, expected):
    result = classify_text(text)
    assert result.document_type == expected
    assert result.confidence > 0.8


def test_text_without_cues_is_unknown():
    result = classify_text("lorem ipsum dolor")
    assert result.document_type is DocumentType.UNKNOWN
    assert result.confidence == 0.0


def test_accuracy_on_synthetic_ground_truth_text():
    labels = generate(REGISTRY, ["uni-a", "uni-b", "uni-c"], 40, seed=11, out_dir=None)
    wrong = Counter(
        (lbl.document_type.value, classify_text(lbl.text).document_type.value)
        for lbl in labels
        if classify_text(lbl.text).document_type != lbl.document_type
    )
    accuracy = 1 - sum(wrong.values()) / len(labels)
    assert accuracy >= 0.97, wrong
