import json
from pathlib import Path

from common.runtime import in_memory_runtime, set_runtime
from common.schemas.events import PipelineEvent
from common.testing import FakeHttpEvent

from functions.cross_check.handler import handle

TENANTS = Path(__file__).resolve().parents[3] / "tenants"


def test_empty_application_runs_no_checks():
    set_runtime(in_memory_runtime(TENANTS))
    try:
        event = PipelineEvent(
            tenant_id="uni-a", application_id="a9", document_id="d9", step="cross-check"
        )
        response = handle(FakeHttpEvent(body=event.model_dump_json()), None)
        assert response["statusCode"] == 200
        assert json.loads(response["body"])["checks"] == 0
    finally:
        set_runtime(None)
