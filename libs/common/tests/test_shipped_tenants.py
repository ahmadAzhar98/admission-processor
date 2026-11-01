"""Every tenant file shipped in tenants/ must load and be active."""

from pathlib import Path

import pytest

from common.tenant_config.loader import TenantRegistry
from common.tenant_config.models import ConfigStatus

TENANTS_DIR = Path(__file__).resolve().parents[3] / "tenants"
REGISTRY = TenantRegistry(TENANTS_DIR)


@pytest.mark.parametrize("tenant_id", REGISTRY.tenant_ids())
def test_shipped_config_is_valid_and_active(tenant_id):
    config = REGISTRY.get(tenant_id)
    assert config.status is ConfigStatus.ACTIVE
    assert config.display_name.startswith("University ")


@pytest.mark.parametrize("tenant_id", REGISTRY.tenant_ids())
def test_identity_fields_are_marked_pii(tenant_id):
    for req in REGISTRY.get(tenant_id).documents:
        for field in req.fields:
            if field.name in {"cnic_number", "b_form_number", "full_name", "father_name"}:
                assert field.pii, f"{tenant_id}/{req.type}/{field.name} must be pii"


def test_tenants_differ_in_requirements():
    a, b, c = (REGISTRY.get(t) for t in ("uni-a", "uni-b", "uni-c"))
    assert "domicile" in b.accepted_types
    assert "domicile" not in a.accepted_types | c.accepted_types
    assert "entry_test" in a.accepted_types and "entry_test" not in c.accepted_types
    assert (
        a.decision.auto_approve_min_confidence
        > b.decision.auto_approve_min_confidence
        > c.decision.auto_approve_min_confidence
    )
    assert b.notifications.default_language == "ur"
