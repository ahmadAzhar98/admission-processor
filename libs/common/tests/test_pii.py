import pytest

from common.pii import mask_data, mask_text, mask_value


@pytest.mark.parametrize(
    "raw",
    ["cnic 35202-1234567-3 found", "cnic 3520212345673 found"],
)
def test_cnic_keeps_only_check_digit(raw):
    masked = mask_text(raw)
    assert "1234567" not in masked
    assert masked == "cnic *****-*******-3 found"


def test_phone_and_email_are_masked():
    masked = mask_text("call 0300-1234567 or mail ali.khan@example.pk")
    assert "1234567" not in masked
    assert "ali.khan" not in masked
    assert "567" in masked
    assert "a***@example.pk" in masked


def test_unrelated_numbers_are_untouched():
    assert mask_text("obtained 950 of 1100 marks") == "obtained 950 of 1100 marks"


def test_mask_value_hides_content():
    assert mask_value("Ayesha Siddiqui") == "A***(15)"
    assert mask_value("") == ""


def test_mask_data_walks_nested_structures():
    data = {
        "full_name": "Ayesha Siddiqui",
        "fields": [{"name": "Bilal", "note": "id 35202-1234567-3"}],
        "obtained_marks": 950,
        "father_name": None,
    }
    masked = mask_data(data)
    assert masked["full_name"] == "A***(15)"
    assert masked["fields"][0]["name"] == "B***(5)"
    assert masked["fields"][0]["note"] == "id *****-*******-3"
    assert masked["obtained_marks"] == 950
    assert masked["father_name"] is None
