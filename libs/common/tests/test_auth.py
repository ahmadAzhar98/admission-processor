from pathlib import Path

import pytest

from common.auth import (
    ApiKeyAuthenticator,
    ChainSecretSource,
    EnvSecretSource,
    FileSecretSource,
    hash_api_key,
)
from common.errors import AuthenticationError, TenantError
from common.tenant_config.loader import TenantRegistry

TENANTS = TenantRegistry(Path(__file__).resolve().parents[3] / "tenants")


class DictSecrets:
    def __init__(self, values):
        self.values = values

    def read(self, name):
        return self.values.get(name)


def _auth():
    return ApiKeyAuthenticator(TENANTS, DictSecrets({"uni-a-api-key": hash_api_key("key-a")}))


def test_valid_key_returns_config():
    assert _auth().authenticate("uni-a", "key-a").tenant_id == "uni-a"


@pytest.mark.parametrize(
    ("tenant", "key"),
    [("uni-a", "wrong"), ("uni-b", "key-a"), ("uni-z", "key-a"), ("uni-a", None), (None, "x")],
)
def test_invalid_credentials_are_indistinguishable(tenant, key):
    with pytest.raises(AuthenticationError) as info:
        _auth().authenticate(tenant, key)
    assert info.value.code == "unauthenticated"


def test_malformed_tenant_id_is_rejected():
    with pytest.raises(TenantError):
        _auth().authenticate("../etc", "key")


def test_secret_sources(tmp_path, monkeypatch):
    (tmp_path / "uni-a-api-key").write_text("abc\n")
    monkeypatch.setenv("AP_SECRET_UNI_B_API_KEY", "def")
    chain = ChainSecretSource(FileSecretSource(tmp_path), EnvSecretSource())
    assert chain.read("uni-a-api-key") == "abc"
    assert chain.read("uni-b-api-key") == "def"
    assert chain.read("uni-c-api-key") is None
    assert FileSecretSource(tmp_path).read("../x") is None
