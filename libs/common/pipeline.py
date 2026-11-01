"""Shared skeleton for asynchronous pipeline steps.

Every step after intake receives a :class:`PipelineEvent` from the queue,
binds the tenant context, does its work, stores its result and publishes
the next event. :func:`run_step` implements the common part so each
step's handler only supplies the work itself.
"""

import logging
import time
from collections.abc import Callable
from typing import Any

from common.errors import InvalidRequestError
from common.http import HttpEvent, Response, json_response, parse_body
from common.runtime import Runtime, get_runtime
from common.schemas.events import PipelineEvent, PipelineStep
from common.tenant import RequestContext, bind_context

logger = logging.getLogger(__name__)

StepFn = Callable[[PipelineEvent, Runtime], dict[str, Any]]


def run_step(http_event: HttpEvent, step: PipelineStep, process: StepFn) -> Response:
    """Parse the queued event, run ``process`` in tenant context, respond.

    Args:
        http_event: The request delivered by the OpenFaaS queue worker.
        step: The step this function implements; events for other steps
            are refused so misrouted work is noticed instead of processed.
        process: The step's work; returns a summary for the response.

    Raises:
        InvalidRequestError: If the body is not an event for ``step``.
    """
    event = parse_body(http_event, PipelineEvent)
    if event.step is not step:
        raise InvalidRequestError(f"event for {event.step} delivered to {step}")
    ctx = RequestContext(
        tenant_id=event.tenant_id,
        document_id=event.document_id,
        correlation_id=event.correlation_id,
    )
    with bind_context(ctx):
        started = time.perf_counter()
        summary = process(event, get_runtime())
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        logger.info("step completed", extra={"step": step.value, "duration_ms": elapsed_ms})
    return json_response(200, {"step": step.value, **summary})
