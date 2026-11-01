"""Run the whole pipeline in one process, without OpenFaaS.

Uploads go through the intake service; every event a step publishes is
dispatched to the next step's ``process`` function in order, as the NATS
queue would. Used by the end-to-end test and the evaluation scripts, and
handy for debugging a tenant config against synthetic documents.
"""

import logging
from collections.abc import Callable
from typing import Any

from common.runtime import InMemoryRuntime, Runtime
from common.schemas.events import PipelineEvent, PipelineStep
from common.tenant import RequestContext, bind_context

from functions.classify import service as classify
from functions.cross_check import service as cross_check
from functions.decide import service as decide
from functions.extract import service as extract
from functions.feedback import service as feedback
from functions.intake.service import UploadRequest, UploadResult, accept_upload
from functions.notify import service as notify
from functions.notify.channels import LogChannel
from functions.quality_check import service as quality_check
from functions.validate import service as validate

logger = logging.getLogger(__name__)

StepFn = Callable[[PipelineEvent, Runtime], dict[str, Any]]


def step_table(channel: LogChannel) -> dict[PipelineStep, StepFn]:
    """Map each step to its ``process`` function; notify logs instead of sending."""
    return {
        PipelineStep.QUALITY_CHECK: quality_check.process,
        PipelineStep.CLASSIFY: classify.process,
        PipelineStep.EXTRACT: extract.process,
        PipelineStep.VALIDATE: validate.process,
        PipelineStep.CROSS_CHECK: cross_check.process,
        PipelineStep.DECIDE: decide.process,
        PipelineStep.NOTIFY: lambda event, rt: notify.process(event, rt, channel),
        PipelineStep.FEEDBACK: feedback.process,
    }


class LocalPipeline:
    """Drives an in-memory runtime through the pipeline."""

    def __init__(self, rt: InMemoryRuntime) -> None:
        """Use ``rt``; its publisher acts as the queue."""
        self.rt = rt
        self.channel = LogChannel()
        self.steps = step_table(self.channel)
        self.trace: list[tuple[PipelineEvent, dict[str, Any]]] = []

    def upload(
        self,
        tenant_id: str,
        application_id: str,
        data: bytes,
        content_type: str = "image/png",
        declared_type: str | None = None,
    ) -> UploadResult:
        """Submit a file as the portal would."""
        request = UploadRequest.model_validate(
            {
                "tenant_id": tenant_id,
                "application_id": application_id,
                "content_type": content_type,
                "declared_type": declared_type,
            }
        )
        with bind_context(RequestContext(tenant_id=tenant_id)):
            return accept_upload(self.rt, request, data)

    def drain(self, max_events: int = 100_000) -> int:
        """Process queued events until none remain; return how many ran."""
        processed = 0
        queue = self.rt.publisher.events
        while queue and processed < max_events:
            event = queue.pop(0)
            ctx = RequestContext(
                tenant_id=event.tenant_id,
                document_id=event.document_id,
                correlation_id=event.correlation_id,
            )
            with bind_context(ctx):
                summary = self.steps[event.step](event, self.rt)
            self.trace.append((event, summary))
            processed += 1
        return processed
