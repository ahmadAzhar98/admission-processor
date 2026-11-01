import pytest

from synthetic.evaluation.metrics import (
    Confusion,
    Tally,
    character_error_rate,
    normalise_for_compare,
    word_error_rate,
)


def test_normalise_for_compare():
    assert normalise_for_compare("  Ali   KHAN ") == "ali khan"
    assert normalise_for_compare(950.0) == normalise_for_compare(950) == "950"
    assert normalise_for_compare(None) == ""


def test_error_rates():
    assert character_error_rate("abcd", "abcd") == 0.0
    assert character_error_rate("abcd", "abxd") == pytest.approx(0.25)
    assert word_error_rate("roll no 123", "roll 123") == pytest.approx(1 / 3)
    assert character_error_rate("", "") == 0.0


def test_tally_groups_and_overall():
    tally = Tally()
    tally.add(("uni-a", "cnic"), True)
    tally.add(("uni-a", "cnic"), False)
    tally.add(("uni-b", "cnic"), True)
    assert tally.rate(("uni-a", "cnic")) == 0.5
    assert tally.overall() == pytest.approx(2 / 3)
    assert [row[0] for row in tally.rows()] == [("uni-a", "cnic"), ("uni-b", "cnic")]


def test_confusion():
    c = Confusion()
    for predicted, actual in [(True, True), (True, False), (False, True), (False, False)]:
        c.add(predicted, actual)
    assert (c.tp, c.fp, c.fn, c.tn) == (1, 1, 1, 1)
    assert c.precision == c.recall == 0.5
