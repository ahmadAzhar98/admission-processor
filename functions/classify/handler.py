"""OpenFaaS entry point for classify (queued pipeline events only)."""

from typing import Any

from common.http import HttpEvent, Response, http_handler
from common.pipeline import run_step
from common.schemas.events import PipelineStep

from .service import process


@http_handler
def handle(event: HttpEvent, context: Any) -> Response:
    """Classify the document named by the queued event."""
    return run_step(event, PipelineStep.CLASSIFY, process)
