import pytest
from pydantic import ValidationError

from common.schemas.documents import DocumentType
from common.schemas.results import ExtractedField, ExtractionResult, FieldSource


def _result(fields):
    return ExtractionResult(
        tenant_id="uni-a",
        document_id="doc-1",
        document_type=DocumentType.CNIC,
        fields=fields,
    )


def test_field_lookup_and_value():
    result = _result([ExtractedField(name="cnic_number", value="35202-0000000-1", confidence=0.9)])
    assert result.get("cnic_number") is not None
    assert result.value("cnic_number") == "35202-0000000-1"
    assert result.value("missing") is None


def test_confidence_is_weakest_field():
    result = _result(
        [
            ExtractedField(name="a", value="x", confidence=0.95),
            ExtractedField(name="b", value="y", confidence=0.6, source=FieldSource.LLM),
        ]
    )
    assert result.confidence == pytest.approx(0.6)


def test_empty_result_has_zero_confidence():
    assert _result([]).confidence == 0.0


@pytest.mark.parametrize("confidence", [-0.1, 1.01])
def test_confidence_bounds(confidence):
    with pytest.raises(ValidationError):
        ExtractedField(name="a", value="x", confidence=confidence)
