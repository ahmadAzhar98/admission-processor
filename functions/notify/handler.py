"""OpenFaaS entry point for notify (queued pipeline events only)."""

from typing import Any

from common.http import HttpEvent, Response, http_handler
from common.pipeline import run_step
from common.schemas.events import PipelineStep

from .service import process


@http_handler
def handle(event: HttpEvent, context: Any) -> Response:
    """Notify the applicant about the queued event."""
    return run_step(event, PipelineStep.NOTIFY, process)
