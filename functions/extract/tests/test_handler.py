import json
from pathlib import Path

import pytest
from common.llm import FakeLlmClient
from common.runtime import in_memory_runtime, set_runtime
from common.schemas.events import PipelineEvent
from common.testing import FakeHttpEvent

from functions.extract.handler import handle

TENANTS = Path(__file__).resolve().parents[3] / "tenants"


@pytest.fixture
def rt():
    runtime = in_memory_runtime(TENANTS)
    runtime.llm = FakeLlmClient()
    set_runtime(runtime)
    yield runtime
    set_runtime(None)


def test_wrong_step_is_rejected(rt):
    event = PipelineEvent(tenant_id="uni-a", application_id="a", document_id="d", step="validate")
    response = handle(FakeHttpEvent(body=event.model_dump_json()), None)
    assert response["statusCode"] == 400
    assert json.loads(response["body"]) == {"error": "invalid_request"}


def test_malformed_body_is_rejected(rt):
    assert handle(FakeHttpEvent(body=b"{"), None)["statusCode"] == 400
