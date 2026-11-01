"""Tenant identity and request-context propagation.

A :class:`RequestContext` carries the tenant ID, document ID and
correlation ID of the request being processed. It is bound to a context
variable so logging and storage code can read it without every function
signature threading it through, while handlers still pass the tenant ID
explicitly to business logic.
"""

import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from common.errors import TenantError

TENANT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,30}[a-z0-9]$")


def validate_tenant_id(tenant_id: str) -> str:
    """Return ``tenant_id`` if it is a safe slug, else raise.

    Tenant IDs appear in object keys, SQL parameters and log lines, so they
    are restricted to lowercase letters, digits and hyphens.

    Raises:
        TenantError: If the ID is empty or contains other characters.
    """
    if not TENANT_ID_PATTERN.fullmatch(tenant_id):
        raise TenantError(f"invalid tenant id: {tenant_id!r}")
    return tenant_id


def new_correlation_id() -> str:
    """Return a fresh random correlation ID."""
    return uuid.uuid4().hex


@dataclass(frozen=True)
class RequestContext:
    """Identifiers of the unit of work currently being processed."""

    tenant_id: str
    document_id: str | None = None
    correlation_id: str = field(default_factory=new_correlation_id)

    def __post_init__(self) -> None:
        """Validate the tenant ID on construction."""
        validate_tenant_id(self.tenant_id)


_current: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)


@contextmanager
def bind_context(ctx: RequestContext) -> Iterator[RequestContext]:
    """Bind ``ctx`` as the current request context for the enclosed block."""
    token = _current.set(ctx)
    try:
        yield ctx
    finally:
        _current.reset(token)


def current_context() -> RequestContext | None:
    """Return the bound request context, or ``None`` outside a request."""
    return _current.get()


def require_tenant_id() -> str:
    """Return the bound tenant ID.

    Raises:
        TenantError: If called outside :func:`bind_context`.
    """
    ctx = _current.get()
    if ctx is None:
        raise TenantError("no tenant bound to the current request")
    return ctx.tenant_id
