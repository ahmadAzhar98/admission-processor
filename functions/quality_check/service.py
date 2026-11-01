"""Quality-check logic: assess an image against tenant thresholds."""

import logging
from typing import Any

from common.errors import InvalidRequestError
from common.runtime import Runtime
from common.schemas.documents import DocumentStatus
from common.schemas.events import PipelineEvent, PipelineStep
from common.schemas.results import QualityReport
from common.tenant_config.models import QualityThresholds

from . import metrics

logger = logging.getLogger(__name__)


def assess(data: bytes, thresholds: QualityThresholds) -> QualityReport:
    """Measure ``data`` and list every threshold it fails.

    An undecodable file yields a rejected report with ``unreadable_file``
    rather than an error, because the right response is still to ask the
    applicant for a new upload.
    """
    try:
        gray = metrics.decode_gray(data)
    except InvalidRequestError:
        return QualityReport(
            accepted=False,
            width=0,
            height=0,
            blur_score=0.0,
            skew_degrees=0.0,
            brightness=0.0,
            contrast=0.0,
            issues=["unreadable_file"],
        )
    height, width = gray.shape
    page = metrics.normalise(gray)
    report = {
        "width": int(width),
        "height": int(height),
        "blur_score": round(metrics.blur_score(page), 2),
        "skew_degrees": round(metrics.skew_degrees(page), 2),
        "brightness": round(float(page.mean()), 2),
        "contrast": round(metrics.contrast(page), 2),
    }
    issues = []
    if width < thresholds.min_width or height < thresholds.min_height:
        issues.append("low_resolution")
    if report["blur_score"] < thresholds.min_blur_score:
        issues.append("blurry")
    if abs(report["skew_degrees"]) > thresholds.max_skew_degrees:
        issues.append("skewed")
    if report["brightness"] < thresholds.min_brightness:
        issues.append("too_dark")
    if report["brightness"] > thresholds.max_brightness:
        issues.append("too_bright")
    if report["contrast"] < thresholds.min_contrast:
        issues.append("low_contrast")
    return QualityReport(accepted=not issues, issues=issues, **report)


def process(event: PipelineEvent, rt: Runtime) -> dict[str, Any]:
    """Assess the stored upload, then continue to classify or ask for re-upload."""
    record = rt.documents.get(event.tenant_id, event.document_id)
    config = rt.tenants.get(event.tenant_id)
    data = rt.tenant_storage(event.tenant_id).get_key(record.document.object_key)
    report = assess(data, config.quality)
    rt.results.save(
        event.tenant_id,
        event.document_id,
        PipelineStep.QUALITY_CHECK.value,
        report.model_dump(),
    )
    if report.accepted:
        rt.publisher.publish(event.next(PipelineStep.CLASSIFY))
    else:
        rt.documents.set_status(
            event.tenant_id,
            event.document_id,
            DocumentStatus.REUPLOAD_REQUIRED,
            actor=PipelineStep.QUALITY_CHECK.value,
            details={"issues": report.issues},
        )
        rt.publisher.publish(
            event.next(
                PipelineStep.NOTIFY,
                {"notification": "reupload_required", "reasons": report.issues},
            )
        )
    logger.info("quality assessed", extra={"accepted": report.accepted, "issues": report.issues})
    return {"accepted": report.accepted, "issues": report.issues}
