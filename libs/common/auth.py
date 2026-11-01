"""Tenant API-key authentication.

Each tenant config names an OpenFaaS secret that holds the SHA-256 hex
digest of the tenant's API key; the key itself is never stored. Requests
present the key, which is hashed and compared in constant time.
"""

import hashlib
import hmac
import os
from pathlib import Path
from typing import Protocol

from common.errors import AuthenticationError, TenantNotFoundError
from common.tenant_config.loader import TenantRegistry
from common.tenant_config.models import TenantConfig


class SecretSource(Protocol):
    """Looks up a named secret value."""

    def read(self, name: str) -> str | None:
        """Return the secret called ``name`` or ``None`` if unknown."""


class FileSecretSource:
    """Secrets mounted as files, as OpenFaaS does under /var/openfaas/secrets."""

    def __init__(self, directory: Path) -> None:
        """Read secret files from ``directory``."""
        self.directory = directory

    def read(self, name: str) -> str | None:
        """Return the stripped file contents, or ``None`` if absent."""
        path = self.directory / name
        if "/" in name or not path.is_file():
            return None
        return path.read_text(encoding="utf-8").strip()


class EnvSecretSource:
    """Secrets from ``AP_SECRET_<NAME>`` variables, for local development."""

    def read(self, name: str) -> str | None:
        """Return ``AP_SECRET_<NAME>`` with hyphens as underscores."""
        return os.environ.get("AP_SECRET_" + name.upper().replace("-", "_"))


class ChainSecretSource:
    """Tries several sources in order."""

    def __init__(self, *sources: SecretSource) -> None:
        """Consult ``sources`` in the given order."""
        self.sources = sources

    def read(self, name: str) -> str | None:
        """Return the first value found."""
        for source in self.sources:
            value = source.read(name)
            if value is not None:
                return value
        return None


def hash_api_key(api_key: str) -> str:
    """Return the SHA-256 hex digest stored for ``api_key``."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


class ApiKeyAuthenticator:
    """Verifies that a request's API key belongs to the claimed tenant."""

    def __init__(self, tenants: TenantRegistry, secrets: SecretSource) -> None:
        """Check keys against hashes found through ``secrets``."""
        self._tenants = tenants
        self._secrets = secrets

    def authenticate(self, tenant_id: str | None, api_key: str | None) -> TenantConfig:
        """Return the tenant config if the key is valid.

        Unknown tenants and wrong keys raise the same error, so the API does
        not reveal which tenant IDs exist.

        Raises:
            AuthenticationError: If the tenant or key is missing or invalid.
        """
        if not tenant_id or not api_key:
            raise AuthenticationError("missing tenant id or api key")
        try:
            config = self._tenants.get(tenant_id)
        except TenantNotFoundError as exc:
            raise AuthenticationError("invalid credentials") from exc
        expected = self._secrets.read(config.auth.api_key_secret)
        if not expected or not hmac.compare_digest(hash_api_key(api_key), expected.lower()):
            raise AuthenticationError("invalid credentials")
        return config
