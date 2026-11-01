import copy
from pathlib import Path

import yaml
from common.llm import FakeLlmClient
from common.tenant_config.loader import parse_config

from functions.onboarding.drafting import (
    DraftRequest,
    build_prompt,
    draft_config,
    enforce_safe_shape,
)

UNI_C = yaml.safe_load((Path(__file__).resolve().parents[3] / "tenants" / "uni-c.yaml").read_text())
REQUEST = DraftRequest(
    tenant_id="uni-d",
    display_name="University D",
    admission_cycle="2027",
    checklist="CNIC or B-form, Matric and FSc result cards with at least 50%, paid fee challan.",
    samples=[{"document_type": "fsc_result", "text": "Higher Secondary School Certificate"}],
)


def _plausible_draft():
    draft = copy.deepcopy(UNI_C)
    draft.pop("notifications")
    draft["tenant_id"] = "someone-else"
    draft["status"] = "active"
    draft["auth"] = {"api_key_secret": "uni-a-api-key"}
    return draft


def test_valid_draft_is_pending_and_cannot_choose_identity_or_secrets():
    result = draft_config(FakeLlmClient(lambda p: _plausible_draft()), REQUEST)
    assert result.valid and result.attempts == 1
    config = parse_config(result.config)
    assert config.tenant_id == "uni-d" and config.status == "pending_approval"
    assert config.auth.api_key_secret == "uni-d-api-key"  # noqa: S105 - a secret name
    assert config.notifications.templates  # defaults filled in


def test_invalid_draft_gets_one_repair_round_with_errors():
    broken = _plausible_draft()
    broken["rules"][0]["obtained_field"] = "marks"
    answers = iter([broken, _plausible_draft()])
    llm = FakeLlmClient(lambda p: next(answers))
    result = draft_config(llm, REQUEST)
    assert result.valid and result.attempts == 2
    assert "field marks not declared" in llm.prompts[1]


def test_persistently_invalid_draft_is_returned_with_errors():
    result = draft_config(FakeLlmClient(lambda p: {"documents": []}), REQUEST)
    assert not result.valid and result.errors
    assert result.config["status"] == "pending_approval"


def test_prompt_contains_checklist_and_samples():
    prompt = build_prompt(REQUEST)
    assert "at least 50%" in prompt and "fsc_result" in prompt
    assert "min_percentage" in prompt


def test_safe_shape_keeps_custom_templates():
    custom = {"notifications": {"templates": {"approved": {"en": "ok {university}", "ur": "ٹھیک"}}}}
    shaped = enforce_safe_shape(REQUEST, custom)
    assert shaped["notifications"]["templates"]["approved"]["en"] == "ok {university}"
    assert "rejected" in shaped["notifications"]["templates"]
