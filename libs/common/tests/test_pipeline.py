import json
from pathlib import Path

import pytest

from common.errors import InvalidRequestError
from common.pipeline import run_step
from common.runtime import in_memory_runtime, set_runtime
from common.schemas.events import PipelineEvent, PipelineStep
from common.tenant import require_tenant_id
from common.testing import FakeHttpEvent

TENANTS = Path(__file__).resolve().parents[3] / "tenants"


@pytest.fixture(autouse=True)
def runtime():
    rt = in_memory_runtime(TENANTS)
    set_runtime(rt)
    yield rt
    set_runtime(None)


def _http(step: str) -> FakeHttpEvent:
    event = PipelineEvent(tenant_id="uni-b", application_id="app-1", document_id="doc-1", step=step)
    return FakeHttpEvent(body=event.model_dump_json())


def test_process_runs_in_tenant_context(runtime):
    seen = {}

    def process(event, rt):
        seen["tenant"] = require_tenant_id()
        seen["runtime"] = rt
        return {"ok": True}

    response = run_step(_http("classify"), PipelineStep.CLASSIFY, process)
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"step": "classify", "ok": True}
    assert seen == {"tenant": "uni-b", "runtime": runtime}


def test_misrouted_event_is_refused():
    with pytest.raises(InvalidRequestError):
        run_step(_http("extract"), PipelineStep.CLASSIFY, lambda e, rt: {})
