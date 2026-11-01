"""Hand work to the next pipeline step.

In a deployment, :class:`GatewayPublisher` posts the event to the
OpenFaaS gateway's ``/async-function/<step>`` endpoint. The gateway
enqueues it on NATS and the queue worker invokes the step, retrying on
failure. Steps therefore never wait on each other, and a deadline-night
burst is buffered by the queue rather than lost to timeouts.
"""

import logging
from typing import Protocol

import httpx

from common.errors import UpstreamServiceError
from common.schemas.events import PipelineEvent

logger = logging.getLogger(__name__)


class EventPublisher(Protocol):
    """Sends a :class:`PipelineEvent` to the step it names."""

    def publish(self, event: PipelineEvent) -> None:
        """Enqueue ``event`` for asynchronous processing."""


class GatewayPublisher:
    """Publishes through OpenFaaS asynchronous invocations (NATS-backed)."""

    def __init__(self, gateway_url: str, client: httpx.Client | None = None) -> None:
        """Post to ``gateway_url``, reusing ``client`` if given."""
        self._base = gateway_url.rstrip("/")
        self._client = client or httpx.Client(timeout=10.0)

    def publish(self, event: PipelineEvent) -> None:
        """POST the event; the gateway answers 202 once it is queued.

        Raises:
            UpstreamServiceError: If the gateway is unreachable or refuses.
        """
        url = f"{self._base}/async-function/{event.step.value}"
        try:
            response = self._client.post(
                url,
                content=event.model_dump_json(),
                headers={
                    "Content-Type": "application/json",
                    "X-Correlation-Id": event.correlation_id,
                },
            )
        except httpx.HTTPError as exc:
            raise UpstreamServiceError(f"gateway unreachable for {event.step}") from exc
        if response.status_code not in (200, 202):
            raise UpstreamServiceError(f"gateway returned {response.status_code} for {event.step}")
        logger.info("event published", extra={"step": event.step.value})


class InMemoryPublisher:
    """Collects published events; used by unit tests and the local runner."""

    def __init__(self) -> None:
        """Start with no events."""
        self.events: list[PipelineEvent] = []

    def publish(self, event: PipelineEvent) -> None:
        """Record ``event``."""
        self.events.append(event)
