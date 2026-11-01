"""OpenFaaS entry point for quality-check.

Two modes share one function:

* **Pipeline step** (JSON body): a queued ``PipelineEvent`` from intake.
* **Precheck** (image body): a portal posts an image with ``X-Tenant-Id``
  and ``X-Api-Key`` before uploading, and gets the quality report back
  synchronously, with ``reupload_required`` set if it would be rejected.
"""

from typing import Any

from common.auth import default_authenticator
from common.http import HttpEvent, Response, body_bytes, header, http_handler, json_response
from common.pipeline import run_step
from common.runtime import get_runtime
from common.schemas.events import PipelineStep
from common.tenant import RequestContext, bind_context

from .service import assess, process


@http_handler
def handle(event: HttpEvent, context: Any) -> Response:
    """Dispatch to the pipeline step or the synchronous precheck."""
    content_type = (header(event, "Content-Type") or "").lower()
    if content_type.startswith("image/"):
        return _precheck(event)
    return run_step(event, PipelineStep.QUALITY_CHECK, process)


def _precheck(event: HttpEvent) -> Response:
    rt = get_runtime()
    config = default_authenticator(rt.tenants).authenticate(
        header(event, "X-Tenant-Id"), header(event, "X-Api-Key")
    )
    with bind_context(RequestContext(tenant_id=config.tenant_id)):
        report = assess(body_bytes(event), config.quality)
    return json_response(
        200, {"reupload_required": not report.accepted, **report.model_dump(mode="json")}
    )
