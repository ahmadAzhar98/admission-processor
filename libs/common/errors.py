"""Exception hierarchy shared by all pipeline functions.

Every error raised deliberately by project code derives from
:class:`AdmissionError`, so handlers can map known failures to HTTP
responses and let anything else surface as an internal error.
"""


class AdmissionError(Exception):
    """Base class for all expected, domain-level failures.

    Attributes:
        http_status: Status code a handler should return for this error.
        code: Stable machine-readable identifier for API clients.
    """

    http_status: int = 500
    code: str = "internal_error"


class TenantError(AdmissionError):
    """A tenant-related failure."""

    http_status = 400
    code = "tenant_error"


class TenantNotFoundError(TenantError):
    """No configuration exists for the requested tenant ID."""

    http_status = 404
    code = "tenant_not_found"


class TenantConfigError(TenantError):
    """A tenant configuration file is missing, unreadable or invalid."""

    http_status = 500
    code = "tenant_config_invalid"


class AuthenticationError(AdmissionError):
    """The caller could not be authenticated for the tenant."""

    http_status = 401
    code = "unauthenticated"


class InvalidRequestError(AdmissionError):
    """The request payload is malformed or incomplete."""

    http_status = 400
    code = "invalid_request"


class StorageError(AdmissionError):
    """Object storage could not complete an operation."""

    http_status = 502
    code = "storage_error"


class ObjectNotFoundError(StorageError):
    """The requested object key does not exist."""

    http_status = 404
    code = "object_not_found"


class DatabaseError(AdmissionError):
    """The database could not complete an operation."""

    http_status = 502
    code = "database_error"


class UpstreamServiceError(AdmissionError):
    """An external dependency (OCR engine, LLM, gateway) failed."""

    http_status = 502
    code = "upstream_error"


class RecordNotFoundError(DatabaseError):
    """No database row matches the requested tenant and ID."""

    http_status = 404
    code = "record_not_found"
