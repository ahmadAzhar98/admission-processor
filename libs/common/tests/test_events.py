import json

import httpx
import pytest

from common.errors import UpstreamServiceError
from common.events import GatewayPublisher, InMemoryPublisher
from common.schemas.events import PipelineEvent, PipelineStep

EVENT = PipelineEvent(
    tenant_id="uni-a", application_id="app-1", document_id="doc-1", step="quality-check"
)


def _publisher(status: int, seen: list[httpx.Request]) -> GatewayPublisher:
    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status)

    client = httpx.Client(transport=httpx.MockTransport(respond))
    return GatewayPublisher("http://gateway:8080/", client)


def test_publishes_to_async_endpoint_of_step():
    seen: list[httpx.Request] = []
    _publisher(202, seen).publish(EVENT)
    request = seen[0]
    assert str(request.url) == "http://gateway:8080/async-function/quality-check"
    assert request.headers["X-Correlation-Id"] == EVENT.correlation_id
    assert json.loads(request.content)["document_id"] == "doc-1"


def test_gateway_refusal_raises():
    with pytest.raises(UpstreamServiceError):
        _publisher(500, []).publish(EVENT)


def test_unreachable_gateway_raises():
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    publisher = GatewayPublisher(
        "http://gateway", httpx.Client(transport=httpx.MockTransport(fail))
    )
    with pytest.raises(UpstreamServiceError):
        publisher.publish(EVENT)


def test_in_memory_publisher_records():
    publisher = InMemoryPublisher()
    publisher.publish(EVENT.next(PipelineStep.CLASSIFY))
    assert publisher.events[0].step is PipelineStep.CLASSIFY
