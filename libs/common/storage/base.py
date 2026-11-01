"""Object store interface, tenant key scoping, and an in-memory store.

Functions never build object keys by hand. :class:`TenantStorage` wraps a
store and prefixes every key with ``tenants/<tenant_id>/``, so code in one
tenant's request cannot read or overwrite another tenant's files.
"""

import re
from typing import Protocol

from common.errors import ObjectNotFoundError, StorageError
from common.tenant import validate_tenant_id

_SAFE_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def tenant_key(tenant_id: str, *parts: str) -> str:
    """Build ``tenants/<tenant_id>/<parts...>`` after validating each part.

    Raises:
        TenantError: If ``tenant_id`` is not a valid slug.
        StorageError: If a part is empty, contains a slash, or starts with a
            dot (which would allow ``..`` traversal).
    """
    validate_tenant_id(tenant_id)
    for part in parts:
        if not _SAFE_PART.fullmatch(part):
            raise StorageError(f"unsafe object key part: {part!r}")
    return "/".join(("tenants", tenant_id, *parts))


class ObjectStore(Protocol):
    """Minimal byte-oriented object store operations."""

    def put(self, key: str, data: bytes, content_type: str) -> None:
        """Store ``data`` under ``key``, overwriting any existing object."""

    def get(self, key: str) -> bytes:
        """Return the bytes stored under ``key``; raise ObjectNotFoundError."""

    def exists(self, key: str) -> bool:
        """Return whether ``key`` exists."""

    def delete(self, key: str) -> None:
        """Delete ``key``; deleting a missing key is not an error."""

    def list(self, prefix: str) -> list[str]:
        """Return all keys starting with ``prefix``, sorted."""


class InMemoryObjectStore:
    """Dictionary-backed store for tests and local experiments."""

    def __init__(self) -> None:
        """Create an empty store."""
        self.objects: dict[str, tuple[bytes, str]] = {}

    def put(self, key: str, data: bytes, content_type: str) -> None:
        """Store ``data`` under ``key``."""
        self.objects[key] = (data, content_type)

    def get(self, key: str) -> bytes:
        """Return the bytes under ``key``."""
        try:
            return self.objects[key][0]
        except KeyError as exc:
            raise ObjectNotFoundError(key) from exc

    def exists(self, key: str) -> bool:
        """Return whether ``key`` exists."""
        return key in self.objects

    def delete(self, key: str) -> None:
        """Delete ``key`` if present."""
        self.objects.pop(key, None)

    def list(self, prefix: str) -> list[str]:
        """Return sorted keys under ``prefix``."""
        return sorted(k for k in self.objects if k.startswith(prefix))


class TenantStorage:
    """An :class:`ObjectStore` view restricted to one tenant's key prefix."""

    def __init__(self, store: ObjectStore, tenant_id: str) -> None:
        """Bind ``store`` to ``tenant_id``."""
        self._store = store
        self.tenant_id = validate_tenant_id(tenant_id)

    def key(self, *parts: str) -> str:
        """Return the full key for ``parts`` within this tenant."""
        return tenant_key(self.tenant_id, *parts)

    def put(self, parts: tuple[str, ...], data: bytes, content_type: str) -> str:
        """Store ``data`` and return the full key it was written to."""
        key = self.key(*parts)
        self._store.put(key, data, content_type)
        return key

    def get(self, *parts: str) -> bytes:
        """Return the bytes stored at ``parts``."""
        return self._store.get(self.key(*parts))

    def get_key(self, key: str) -> bytes:
        """Return bytes for a full key, refusing keys of other tenants."""
        if not key.startswith(f"tenants/{self.tenant_id}/"):
            raise StorageError("object key belongs to another tenant")
        return self._store.get(key)

    def exists(self, *parts: str) -> bool:
        """Return whether an object exists at ``parts``."""
        return self._store.exists(self.key(*parts))

    def list(self, *parts: str) -> list[str]:
        """Return full keys under ``parts`` within this tenant."""
        prefix = self.key(*parts) + "/" if parts else f"tenants/{self.tenant_id}/"
        return self._store.list(prefix)
