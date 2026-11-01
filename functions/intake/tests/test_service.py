from pathlib import Path

import pytest
from common.errors import InvalidRequestError, PayloadTooLargeError
from common.runtime import in_memory_runtime
from common.schemas.events import PipelineStep
from common.settings import Settings

from functions.intake.service import UploadRequest, accept_upload

TENANTS = Path(__file__).resolve().parents[3] / "tenants"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


@pytest.fixture
def rt():
    return in_memory_runtime(
        TENANTS, Settings(environment="test", tenants_dir=TENANTS, max_upload_bytes=1000)
    )


def _request(**overrides):
    data = {"tenant_id": "uni-a", "application_id": "app-1", "content_type": "image/png"}
    data.update(overrides)
    return UploadRequest(**data)


def test_upload_is_stored_under_tenant_prefix_and_enqueued(rt):
    result = accept_upload(rt, _request(declared_type="cnic"), PNG)
    assert not result.duplicate
    record = rt.documents.get("uni-a", result.document_id)
    assert record.document.object_key.startswith("tenants/uni-a/applications/app-1/")
    assert rt.storage.get(record.document.object_key) == PNG
    [event] = rt.publisher.events
    assert event.step is PipelineStep.QUALITY_CHECK
    assert event.document_id == result.document_id


def test_reupload_is_idempotent(rt):
    first = accept_upload(rt, _request(), PNG)
    second = accept_upload(rt, _request(), PNG)
    assert second.duplicate and second.document_id == first.document_id
    assert len(rt.publisher.events) == 1


def test_same_file_for_two_applications_is_two_documents(rt):
    a = accept_upload(rt, _request(application_id="app-1"), PNG)
    b = accept_upload(rt, _request(application_id="app-2"), PNG)
    assert a.document_id != b.document_id


@pytest.mark.parametrize(
    ("content_type", "data", "error"),
    [
        ("application/pdf", PNG, InvalidRequestError),
        ("image/png", b"", InvalidRequestError),
        ("image/png", b"0" * 1001, PayloadTooLargeError),
    ],
)
def test_rejected_uploads(rt, content_type, data, error):
    with pytest.raises(error):
        accept_upload(rt, _request(content_type=content_type), data)
    assert rt.publisher.events == []


def test_content_type_parameters_are_ignored(rt):
    result = accept_upload(rt, _request(content_type="image/JPEG; charset=binary"), PNG)
    assert rt.documents.get("uni-a", result.document_id).document.content_type == "image/jpeg"
