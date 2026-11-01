from datetime import date

import pytest
from common.tenant_config.fields import FieldType

from functions.extract.normalize import coerce, normalise_date, parse_iso_date


@pytest.mark.parametrize(
    "raw", ["05-03-2007", "05/03/2007", "05.03.2007", "05 Mar 2007", "5 March 2007", "2007-03-05"]
)
def test_dates_normalise_to_iso(raw):
    assert normalise_date(raw) == "2007-03-05"


def test_invalid_date_is_none():
    assert normalise_date("31-02-2007") is None
    assert normalise_date("soon") is None


@pytest.mark.parametrize(
    ("raw", "field_type", "expected"),
    [
        ("5,000/-", FieldType.INTEGER, 5000),
        ("Rs. 950", FieldType.INTEGER, 950),
        ("132.5", FieldType.NUMBER, 132.5),
        ("  Ayesha   Khan : ", FieldType.STRING, "Ayesha Khan"),
        ("n/a", FieldType.INTEGER, None),
        ("", FieldType.STRING, None),
    ],
)
def test_coerce(raw, field_type, expected):
    assert coerce(raw, field_type) == expected


def test_parse_iso_date():
    assert parse_iso_date("2007-03-05") == date(2007, 3, 5)
    assert parse_iso_date(2007) is None
    assert parse_iso_date("bad") is None
