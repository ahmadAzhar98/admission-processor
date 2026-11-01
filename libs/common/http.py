"""Adapters between OpenFaaS ``python3-http`` handlers and project code.

The template calls ``handle(event, context)`` with an event exposing
``body``, ``headers``, ``method``, ``query`` and ``path``, and expects a
dict with ``statusCode``, ``body`` and ``headers``. These helpers parse
requests into Pydantic models and turn domain errors into consistent
JSON error responses that never echo request content.
"""

import functools
import json
import logging
from collections.abc import Callable, Mapping
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from common.errors import AdmissionError, InvalidRequestError

logger = logging.getLogger(__name__)

Response = dict[str, Any]
M = TypeVar("M", bound=BaseModel)


class HttpEvent(Protocol):
    """The request object passed by the OpenFaaS python3-http template."""

    @property
    def body(self) -> bytes | str:
        """Raw request body."""

    @property
    def headers(self) -> Mapping[str, str]:
        """Request headers."""

    @property
    def method(self) -> str:
        """HTTP method."""

    @property
    def query(self) -> Mapping[str, str]:
        """Query-string parameters."""

    @property
    def path(self) -> str:
        """Request path."""


def json_response(status: int, payload: Any) -> Response:
    """Return a JSON response in the template's dict format."""
    if isinstance(payload, BaseModel):
        body = payload.model_dump_json()
    else:
        body = json.dumps(payload, default=str, ensure_ascii=False)
    return {"statusCode": status, "body": body, "headers": {"Content-Type": "application/json"}}


def error_response(exc: AdmissionError) -> Response:
    """Map a domain error to its HTTP status and stable error code."""
    return json_response(exc.http_status, {"error": exc.code})


def header(event: HttpEvent, name: str) -> str | None:
    """Return a header value, matching the name case-insensitively."""
    value = event.headers.get(name)
    if value is not None:
        return value
    lowered = name.lower()
    return next((v for k, v in event.headers.items() if k.lower() == lowered), None)


def body_bytes(event: HttpEvent) -> bytes:
    """Return the raw request body as bytes."""
    body = event.body
    return body.encode("utf-8") if isinstance(body, str) else bytes(body or b"")


def parse_body(event: HttpEvent, model: type[M]) -> M:
    """Parse the JSON body into ``model``.

    Raises:
        InvalidRequestError: If the body is not valid JSON for ``model``.
    """
    try:
        return model.model_validate_json(body_bytes(event))
    except ValidationError as exc:
        fields = sorted({".".join(str(p) for p in err["loc"]) for err in exc.errors()})
        raise InvalidRequestError(f"invalid fields: {fields}") from exc


Handler = Callable[[HttpEvent, Any], Response]


def http_handler(fn: Handler) -> Handler:
    """Wrap a handler so failures become JSON error responses.

    Domain errors map to their status code. Anything unexpected is logged
    with its traceback (masked by the JSON formatter) and returned as a
    generic 500 so internals never leak to callers.
    """

    @functools.wraps(fn)
    def wrapper(event: HttpEvent, context: Any) -> Response:
        try:
            return fn(event, context)
        except AdmissionError as exc:
            log = logger.warning if exc.http_status < 500 else logger.error
            log("request failed", extra={"error": exc.code, "detail": str(exc)})
            return error_response(exc)
        except Exception:
            logger.exception("unhandled error")
            return json_response(500, {"error": "internal_error"})

    return wrapper
