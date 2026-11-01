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
