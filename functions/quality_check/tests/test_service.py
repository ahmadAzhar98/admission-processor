from pathlib import Path

import pytest
from common.runtime import in_memory_runtime
from common.schemas.documents import Document, DocumentStatus
from common.schemas.events import PipelineEvent, PipelineStep
from common.tenant_config.models import QualityThresholds
from PIL import Image, ImageFilter

from functions.quality_check.service import assess, process

TENANTS = Path(__file__).resolve().parents[3] / "tenants"
DEFAULTS = QualityThresholds()


def test_clean_page_is_accepted(page_bytes):
    report = assess(page_bytes(), DEFAULTS)
    assert report.accepted, report
    assert report.issues == []


@pytest.mark.parametrize(
    ("transform", "issue"),
    [
        (lambda im: im.filter(ImageFilter.GaussianBlur(3)), "blurry"),
        (lambda im: im.rotate(9, fillcolor=(245, 245, 240)), "skewed"),
        (lambda im: im.resize((400, 520)), "low_resolution"),
        (lambda im: Image.eval(im, lambda v: v // 5), "too_dark"),
    ],
)
def test_degraded_pages_list_their_issue(page_bytes, transform, issue):
    report = assess(page_bytes(transform=transform), DEFAULTS)
    assert not report.accepted
    assert issue in report.issues


def test_unreadable_file_asks_for_reupload():
    report = assess(b"garbage", DEFAULTS)
    assert report.issues == ["unreadable_file"]


def test_same_image_is_judged_by_tenant_thresholds(page_bytes):
    rt = in_memory_runtime(TENANTS)
    slightly_skewed = page_bytes(transform=lambda im: im.rotate(6, fillcolor=(245, 245, 240)))
    strict = assess(slightly_skewed, rt.tenants.get("uni-a").quality)
    lenient = assess(slightly_skewed, rt.tenants.get("uni-c").quality)
    assert "skewed" in strict.issues
    assert lenient.accepted


def _stored(rt, tenant_id: str, data: bytes) -> PipelineEvent:
    key = rt.tenant_storage(tenant_id).put(
        ("applications", "app-1", "doc-1.png"), data, "image/png"
    )
    rt.documents.add(
        Document(
            tenant_id=tenant_id,
            document_id="doc-1",
            application_id="app-1",
            object_key=key,
            content_type="image/png",
            sha256="0" * 64,
            size_bytes=len(data),
        )
    )
    return PipelineEvent(
        tenant_id=tenant_id, application_id="app-1", document_id="doc-1", step="quality-check"
    )


def test_accepted_document_moves_to_classify(page_bytes):
    rt = in_memory_runtime(TENANTS)
    summary = process(_stored(rt, "uni-b", page_bytes()), rt)
    assert summary["accepted"] is True
    assert [e.step for e in rt.publisher.events] == [PipelineStep.CLASSIFY]
    stored = rt.results.get("uni-b", "doc-1", "quality-check")
    assert stored is not None and stored["accepted"] is True


def test_rejected_document_requests_reupload(page_bytes):
    rt = in_memory_runtime(TENANTS)
    blurred = page_bytes(transform=lambda im: im.filter(ImageFilter.GaussianBlur(4)))
    process(_stored(rt, "uni-b", blurred), rt)
    assert rt.documents.get("uni-b", "doc-1").status is DocumentStatus.REUPLOAD_REQUIRED
    [event] = rt.publisher.events
    assert event.step is PipelineStep.NOTIFY
    assert event.payload == {"notification": "reupload_required", "reasons": ["blurry"]}


def test_reprocessing_overwrites_the_result(page_bytes):
    rt = in_memory_runtime(TENANTS)
    event = _stored(rt, "uni-b", page_bytes())
    process(event, rt)
    process(event, rt)
    assert len(rt.results.results) == 1
