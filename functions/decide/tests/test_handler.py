import json
from pathlib import Path

from common.runtime import in_memory_runtime, set_runtime
from common.schemas.events import PipelineEvent
from common.testing import FakeHttpEvent

from functions.decide.handler import handle

TENANTS = Path(__file__).resolve().parents[3] / "tenants"


def test_application_without_documents_is_incomplete():
    rt = in_memory_runtime(TENANTS)
    set_runtime(rt)
    try:
        event = PipelineEvent(
            tenant_id="uni-b", application_id="a1", document_id="d1", step="decide"
        )
        body = json.loads(handle(FakeHttpEvent(body=event.model_dump_json()), None)["body"])
        assert body["outcome"] == "incomplete"
        assert "missing:domicile" in body["reasons"]
        assert rt.publisher.events == []
    finally:
        set_runtime(None)
