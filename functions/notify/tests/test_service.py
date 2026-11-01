from pathlib import Path

import pytest
from common.errors import InvalidRequestError, UpstreamServiceError
from common.runtime import in_memory_runtime
from common.schemas.documents import Document, DocumentStatus, DocumentType
from common.schemas.events import PipelineEvent

from functions.notify.channels import LogChannel
from functions.notify.service import process

TENANTS = Path(__file__).resolve().parents[3] / "tenants"


def _setup(tenant_id):
    rt = in_memory_runtime(TENANTS)
    rt.documents.add(
        Document(
            tenant_id=tenant_id,
            document_id="d1",
            application_id="app-7",
            object_key=f"tenants/{tenant_id}/x",
            content_type="image/png",
            sha256="8" * 64,
            size_bytes=1,
        )
    )
    rt.documents.set_status(
        tenant_id, "d1", DocumentStatus.VALIDATED, actor="t", document_type=DocumentType.FSC_RESULT
    )
    return rt


def _event(tenant_id, notification, reasons=()):
    return PipelineEvent(
        tenant_id=tenant_id,
        application_id="app-7",
        document_id="d1",
        step="notify",
        payload={"notification": notification, "reasons": list(reasons)},
    )


def test_message_uses_tenant_language_and_template():
    english, urdu = LogChannel(), LogChannel()
    process(_event("uni-a", "approved"), _setup("uni-a"), english)
    process(_event("uni-b", "approved"), _setup("uni-b"), urdu)
    assert english.sent[0].language == "en" and "University A" in english.sent[0].text
    assert urdu.sent[0].language == "ur" and "تصدیق" in urdu.sent[0].text


def test_redelivery_sends_once():
    rt, channel = _setup("uni-c"), LogChannel()
    assert process(_event("uni-c", "rejected", ["rule:fsc-min-45"]), rt, channel)["sent"] is True
    assert process(_event("uni-c", "rejected", ["rule:fsc-min-45"]), rt, channel)["sent"] is False
    assert len(channel.sent) == 1
    assert "rule:fsc-min-45" in channel.sent[0].text
    assert rt.audit.entries[-1].action == "notification_sent"


def test_failed_delivery_can_be_retried():
    class Failing:
        def send(self, message):
            raise UpstreamServiceError("down")

    rt = _setup("uni-c")
    with pytest.raises(UpstreamServiceError):
        process(_event("uni-c", "approved"), rt, Failing())
    assert process(_event("uni-c", "approved"), rt, LogChannel())["sent"] is True


def test_unknown_notification_is_rejected():
    with pytest.raises(InvalidRequestError):
        process(_event("uni-c", "party"), _setup("uni-c"), LogChannel())
