"""OpenFaaS entry point for feedback (queued events from the review API)."""

from typing import Any

from common.http import HttpEvent, Response, http_handler
from common.pipeline import run_step
from common.schemas.events import PipelineStep

from .service import process


@http_handler
def handle(event: HttpEvent, context: Any) -> Response:
    """Learn from the reviewed document named by the event."""
    return run_step(event, PipelineStep.FEEDBACK, process)
