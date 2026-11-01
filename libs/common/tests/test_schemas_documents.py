import pytest
from pydantic import ValidationError

from common.schemas.documents import Document, DocumentType

SHA = "a" * 64


def _doc(**overrides):
    data = {
        "tenant_id": "uni-a",
        "document_id": "doc-1",
        "application_id": "app-1",
        "object_key": "tenants/uni-a/applications/app-1/doc-1.png",
        "content_type": "image/png",
        "sha256": SHA,
        "size_bytes": 10,
    }
    data.update(overrides)
    return Document(**data)


def test_valid_document():
    doc = _doc(declared_type="fsc_result")
    assert doc.declared_type is DocumentType.FSC_RESULT
    assert doc.uploaded_at.tzinfo is not None


@pytest.mark.parametrize(
    "overrides",
    [
        {"tenant_id": "Uni A"},
        {"document_id": "../x"},
        {"sha256": "nothex"},
        {"size_bytes": -1},
        {"declared_type": "passport"},
    ],
)
def test_invalid_documents_are_rejected(overrides):
    with pytest.raises(ValidationError):
        _doc(**overrides)


def test_document_is_immutable():
    doc = _doc()
    with pytest.raises(ValidationError):
        doc.document_id = "other"
