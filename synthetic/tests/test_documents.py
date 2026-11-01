import random
from datetime import date

import pytest
from common.schemas.documents import DocumentType

from synthetic import documents
from synthetic.identities import make_applicant

APPLICANT = make_applicant(random.Random(11), ("Lahore",))


@pytest.mark.parametrize("builder", [documents.cnic, documents.b_form, documents.domicile])
@pytest.mark.parametrize("language", ["en", "ur", "mixed"])
def test_identity_documents_carry_identity_fields(builder, language):
    content = builder(APPLICANT, random.Random(1), language)
    assert content.fields["full_name"] == APPLICANT.full_name
    assert content.fields["father_name"] == APPLICANT.father_name
    assert len(content.lines) == len(content.fields)
    assert APPLICANT.full_name in content.text


def test_ground_truth_dates_are_iso_but_printed_locally():
    content = documents.cnic(APPLICANT, random.Random(2), "en")
    assert content.fields["date_of_birth"] == APPLICANT.date_of_birth.isoformat()
    printed = dict(content.lines)["Date of Birth"]
    assert printed != content.fields["date_of_birth"]


def test_urdu_labels_are_used():
    content = documents.domicile(APPLICANT, random.Random(3), "ur")
    assert content.document_type is DocumentType.DOMICILE
    assert "ضلع" in dict(content.lines)


@pytest.mark.parametrize(
    ("style", "expected"),
    [("dash", "05-03-2007"), ("slash", "05/03/2007"), ("long", "05 Mar 2007")],
)
def test_format_date(style, expected):
    assert documents.format_date(date(2007, 3, 5), style) == expected


@pytest.mark.parametrize("builder", [documents.matric_result, documents.fsc_result])
def test_result_cards_have_consistent_marks(builder):
    for seed in range(50):
        content = builder(APPLICANT, random.Random(seed), "en")
        fields = content.fields
        assert 0 < fields["obtained_marks"] < fields["total_marks"]
        assert fields["board"] in documents.BOARDS
        assert content.layout in documents.RESULT_LAYOUTS


def test_fsc_follows_matric():
    matric = documents.matric_result(APPLICANT, random.Random(1), "en")
    fsc = documents.fsc_result(APPLICANT, random.Random(1), "en")
    assert fsc.fields["passing_year"] == int(matric.fields["passing_year"]) + 2
    assert "group" in fsc.fields and "group" not in matric.fields


def test_marks_span_pass_and_fail():
    percents = [
        int(c.fields["obtained_marks"]) / int(c.fields["total_marks"])
        for c in (documents.fsc_result(APPLICANT, random.Random(s), "en") for s in range(300))
    ]
    assert min(percents) < 0.45 < 0.7 < max(percents)


def test_every_known_type_has_a_builder():
    expected = set(DocumentType) - {DocumentType.UNKNOWN}
    assert set(documents.BUILDERS) == expected


@pytest.mark.parametrize("document_type", sorted(documents.BUILDERS))
def test_builders_are_deterministic(document_type):
    a = documents.build_document(document_type, APPLICANT, random.Random(5), "mixed")
    b = documents.build_document(document_type, APPLICANT, random.Random(5), "mixed")
    assert a == b
    assert a.document_type is document_type


def test_entry_test_score_within_scale():
    for seed in range(50):
        fields = documents.entry_test(APPLICANT, random.Random(seed), "en").fields
        assert 0 <= float(fields["score"]) <= float(fields["total_score"])
        assert fields["cnic_number"] == APPLICANT.cnic_number


def test_challan_prints_amount_with_separator():
    content = documents.fee_challan(APPLICANT, random.Random(1), "en")
    printed = dict(content.lines)["Amount (Rs.)"]
    assert printed.endswith("/-") and isinstance(content.fields["amount"], int)
