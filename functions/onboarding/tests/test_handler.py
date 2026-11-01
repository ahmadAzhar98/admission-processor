import base64
import copy
import json
from pathlib import Path

import pytest
import yaml
from common.auth import hash_api_key
from common.llm import FakeLlmClient
from common.ocr import StaticOcrEngine
from common.runtime import in_memory_runtime, set_runtime
from common.testing import FakeHttpEvent

from functions.onboarding.handler import handle

TENANTS = Path(__file__).resolve().parents[3] / "tenants"
UNI_C = yaml.safe_load((TENANTS / "uni-c.yaml").read_text())
BODY = {
    "tenant_id": "uni-d",
    "display_name": "University D",
    "admission_cycle": "2027",
    "checklist": "CNIC, Matric and FSc with at least 45%, and a paid fee challan.",
    "samples": [{"image": base64.b64encode(b"img").decode()}, {"text": "Fee Challan - Paid"}],
}


@pytest.fixture
def rt(monkeypatch):
    monkeypatch.setenv("AP_SECRET_PLATFORM_ADMIN_KEY", hash_api_key("admin"))
    runtime = in_memory_runtime(TENANTS)
    runtime.ocr = StaticOcrEngine("Higher Secondary School Certificate")
    runtime.llm = FakeLlmClient(lambda p: copy.deepcopy(UNI_C))
    set_runtime(runtime)
    yield runtime
    set_runtime(None)


def _post(key="admin", body=BODY):
    return handle(FakeHttpEvent(body=json.dumps(body), headers={"X-Admin-Key": key}), None)


def test_draft_is_stored_pending_and_audited(rt):
    response = _post()
    body = json.loads(response["body"])
    assert response["statusCode"] == 200 and body["valid"] is True
    stored = json.loads(rt.storage.get("tenants/uni-d/onboarding/draft.json"))
    assert stored["status"] == "pending_approval"
    assert "Higher Secondary School Certificate" in rt.get_llm().prompts[0]  # OCR of the image
    assert rt.audit.entries[-1].action == "config_drafted"


def test_requires_admin_key(rt):
    assert _post(key="wrong")["statusCode"] == 401
    assert rt.storage.list("tenants/") == []


def test_bad_image_is_400(rt):
    body = {**BODY, "samples": [{"image": "%%%"}]}
    assert _post(body=body)["statusCode"] == 400
