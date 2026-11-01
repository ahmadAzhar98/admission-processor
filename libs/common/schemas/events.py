"""Events passed between pipeline steps through asynchronous invocations."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from common.schemas.documents import Identifier, TenantId
from common.tenant import new_correlation_id


class PipelineStep(StrEnum):
    """Pipeline steps in processing order; values are OpenFaaS function names."""

    INTAKE = "intake"
    QUALITY_CHECK = "quality-check"
    CLASSIFY = "classify"
    EXTRACT = "extract"
    VALIDATE = "validate"
    CROSS_CHECK = "cross-check"
    DECIDE = "decide"
    NOTIFY = "notify"


class PipelineEvent(BaseModel):
    """Work item handed from one step to the next.

    The event names the step that should handle it. ``payload`` carries the
    previous step's output so the next step need not re-read it.
    """

    model_config = ConfigDict(frozen=True)

    tenant_id: TenantId
    application_id: Identifier
    document_id: Identifier
    step: PipelineStep
    correlation_id: str = Field(default_factory=new_correlation_id)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def idempotency_key(self) -> str:
        """Key identifying this unit of work; redelivery yields the same key."""
        return f"{self.tenant_id}:{self.document_id}:{self.step.value}"

    def next(self, step: PipelineStep, payload: dict[str, Any] | None = None) -> "PipelineEvent":
        """Return the event for ``step`` keeping identity and correlation ID."""
        return self.model_copy(
            update={
                "step": step,
                "payload": payload or {},
                "created_at": datetime.now(UTC),
            }
        )
