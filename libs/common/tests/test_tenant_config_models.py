import copy
from typing import Any

import pytest
from pydantic import ValidationError

from common.schemas.documents import DocumentType
from common.tenant_config.models import ConfigStatus, TenantConfig
from common.tenant_config.notifications import NotificationEvent

TEMPLATE = {"en": "{university}: {application_id}", "ur": "{university}: {application_id}"}

BASE: dict[str, Any] = {
    "tenant_id": "uni-x",
    "display_name": "University X",
    "admission_cycle": "2026",
    "auth": {"api_key_secret": "uni-x-api-key"},
    "documents": [
        {
            "type": "cnic",
            "alternatives": ["b_form"],
            "fields": [{"name": "cnic_number"}, {"name": "full_name", "pii": True}],
        },
        {"type": "b_form", "required": False, "fields": [{"name": "full_name"}]},
        {
            "type": "fsc_result",
            "fields": [
                {"name": "full_name"},
                {"name": "obtained_marks", "type": "integer"},
                {"name": "total_marks", "type": "integer"},
            ],
        },
    ],
    "rules": [
        {
            "id": "fsc-min",
            "description": "at least 60%",
            "document": "fsc_result",
            "type": "min_percentage",
            "obtained_field": "obtained_marks",
            "total_field": "total_marks",
            "min_percent": 60,
        }
    ],
    "cross_checks": [
        {"field": "full_name", "documents": ["cnic", "fsc_result"], "method": "fuzzy"}
    ],
    "notifications": {"templates": {e.value: TEMPLATE for e in NotificationEvent}},
}


def _config(mutate=None):
    data = copy.deepcopy(BASE)
    if mutate:
        mutate(data)
    return TenantConfig.model_validate(data)


def test_valid_config_and_defaults():
    config = _config()
    assert config.status is ConfigStatus.ACTIVE
    assert config.decision.auto_approve_min_confidence == 0.9
    assert config.requirement(DocumentType.CNIC) is not None
    assert config.requirement(DocumentType.DOMICILE) is None
    assert DocumentType.B_FORM in config.accepted_types


def test_rule_referencing_unknown_field_is_rejected():
    def mutate(d):
        d["rules"][0]["obtained_field"] = "marks"

    with pytest.raises(ValidationError, match="field marks not declared"):
        _config(mutate)


def test_rule_referencing_undeclared_document_is_rejected():
    def mutate(d):
        d["rules"][0]["document"] = "domicile"

    with pytest.raises(ValidationError, match="not declared"):
        _config(mutate)


def test_cross_check_field_must_exist_in_each_document():
    def mutate(d):
        d["cross_checks"][0]["field"] = "cnic_number"

    with pytest.raises(ValidationError, match="cross-check cnic_number"):
        _config(mutate)


def test_alternative_needs_its_own_spec():
    def mutate(d):
        d["documents"].pop(1)

    with pytest.raises(ValidationError, match="alternative"):
        _config(mutate)


def test_duplicate_rule_ids_are_rejected():
    def mutate(d):
        d["rules"].append(copy.deepcopy(d["rules"][0]))

    with pytest.raises(ValidationError, match="unique"):
        _config(mutate)
