import pytest

from common.errors import TenantError
from common.tenant import (
    RequestContext,
    bind_context,
    current_context,
    require_tenant_id,
    validate_tenant_id,
)


@pytest.mark.parametrize("tenant_id", ["uni-a", "university-b", "abc"])
def test_valid_tenant_ids(tenant_id):
    assert validate_tenant_id(tenant_id) == tenant_id


@pytest.mark.parametrize("tenant_id", ["", "A", "Uni-A", "uni_a", "../etc", "uni-", "u"])
def test_invalid_tenant_ids(tenant_id):
    with pytest.raises(TenantError):
        validate_tenant_id(tenant_id)


def test_context_binding_is_scoped():
    assert current_context() is None
    with bind_context(RequestContext(tenant_id="uni-a", document_id="d1")) as ctx:
        assert require_tenant_id() == "uni-a"
        assert current_context() is ctx
        assert len(ctx.correlation_id) == 32
    assert current_context() is None


def test_nested_binding_restores_outer_context():
    with bind_context(RequestContext(tenant_id="uni-a")):
        with bind_context(RequestContext(tenant_id="uni-b")):
            assert require_tenant_id() == "uni-b"
        assert require_tenant_id() == "uni-a"


def test_require_tenant_outside_request_raises():
    with pytest.raises(TenantError):
        require_tenant_id()


def test_context_rejects_bad_tenant():
    with pytest.raises(TenantError):
        RequestContext(tenant_id="Bad Tenant")
