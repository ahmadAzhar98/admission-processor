import pytest
from common.schemas.documents import DocumentType
from common.tenant_config.models import CrossCheck

from functions.cross_check.matching import Observation, check, similarity

NAME = CrossCheck(
    field="full_name",
    documents=["cnic", "matric_result", "fsc_result"],
    method="fuzzy",
    min_similarity=0.9,
)
CNIC = CrossCheck(field="cnic_number", documents=["cnic", "entry_test"], method="exact")


def _obs(doc_type, value):
    return Observation(
        document_type=DocumentType(doc_type), document_id=f"{doc_type}-1", value=value
    )


@pytest.mark.parametrize(
    ("a", "b", "method", "expected"),
    [
        ("Ali Khan", "Khan Ali", "fuzzy", 1.0),
        ("35202-1234567-3", "3520212345673", "exact", 1.0),
        ("35202-1234567-3", "35202-1234567-5", "exact", 0.0),
    ],
)
def test_similarity(a, b, method, expected):
    assert similarity(a, b, method) == expected


def test_ocr_slip_still_matches_but_different_person_fails():
    ok = check(NAME, [_obs("cnic", "Ayesha Siddiqui"), _obs("fsc_result", "Ayesha Sidiqui")])
    bad = check(NAME, [_obs("cnic", "Ayesha Siddiqui"), _obs("fsc_result", "Fatima Raza")])
    assert ok is not None and ok.passed
    assert bad is not None and not bad.passed
    assert "Fatima" not in bad.message and "fsc_result" in bad.message


def test_worst_pair_decides():
    outcome = check(
        NAME,
        [
            _obs("fsc_result", "Ali Khan"),
            _obs("cnic", "Ali Khan"),
            _obs("matric_result", "Bilal Ahmed"),
        ],
    )
    assert outcome is not None and not outcome.passed
    assert "between cnic and matric_result" in outcome.message


def test_single_document_has_nothing_to_compare():
    assert check(CNIC, [_obs("cnic", "35202-1234567-3")]) is None
    assert check(CNIC, [_obs("cnic", "35202-1234567-3"), _obs("entry_test", None)]) is None
