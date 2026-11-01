"""OpenFaaS entry point for cross-check (queued pipeline events only)."""

from typing import Any

from common.http import HttpEvent, Response, http_handler
from common.pipeline import run_step
from common.schemas.events import PipelineStep

from .service import process


@http_handler
def handle(event: HttpEvent, context: Any) -> Response:
    """Cross-check the application of the queued event."""
    return run_step(event, PipelineStep.CROSS_CHECK, process)
