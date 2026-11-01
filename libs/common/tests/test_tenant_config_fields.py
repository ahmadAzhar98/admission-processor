import pytest
from pydantic import ValidationError

from common.schemas.documents import DocumentType
from common.tenant_config.fields import DocumentRequirement, FieldSpec, FieldType


def test_field_defaults():
    spec = FieldSpec(name="roll_number")
    assert spec.type is FieldType.STRING
    assert spec.required and not spec.pii


@pytest.mark.parametrize("name", ["Roll", "1abc", "roll-number", ""])
def test_field_names_are_snake_case(name):
    with pytest.raises(ValidationError):
        FieldSpec(name=name)


def test_invalid_regex_is_rejected():
    with pytest.raises(ValidationError):
        FieldSpec(name="cnic_number", pattern="([0-9")


def test_unknown_keys_are_rejected():
    with pytest.raises(ValidationError):
        FieldSpec.model_validate({"name": "x", "requird": True})


def test_requirement_lookup_and_duplicates():
    req = DocumentRequirement(
        type=DocumentType.CNIC,
        alternatives=[DocumentType.B_FORM],
        fields=[FieldSpec(name="cnic_number"), FieldSpec(name="full_name", pii=True)],
    )
    full_name = req.field("full_name")
    assert full_name is not None and full_name.pii
    assert req.field("missing") is None
    with pytest.raises(ValidationError):
        DocumentRequirement(
            type=DocumentType.CNIC, fields=[FieldSpec(name="a"), FieldSpec(name="a")]
        )


def test_requirement_cannot_be_its_own_alternative():
    with pytest.raises(ValidationError):
        DocumentRequirement(
            type=DocumentType.CNIC,
            alternatives=[DocumentType.CNIC],
            fields=[FieldSpec(name="a")],
        )
