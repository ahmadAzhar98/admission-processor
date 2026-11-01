"""Structured JSON logging with tenant context and PII masking.

Every record is emitted as one JSON object carrying ``tenant_id``,
``document_id`` and ``correlation_id`` from the bound request context.
Fields passed through ``extra=`` are included after masking, and the
message itself is scanned for identifier patterns.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from common.pii import mask_data, mask_text
from common.tenant import current_context

_STANDARD_ATTRS = frozenset(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """Render log records as single-line, PII-masked JSON."""

    def format(self, record: logging.LogRecord) -> str:
        """Return the JSON representation of ``record``."""
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": mask_text(record.getMessage()),
        }
        ctx = current_context()
        if ctx is not None:
            payload["tenant_id"] = ctx.tenant_id
            payload["document_id"] = ctx.document_id
            payload["correlation_id"] = ctx.correlation_id
        extra = {k: v for k, v in vars(record).items() if k not in _STANDARD_ATTRS}
        payload.update(mask_data(extra))
        if record.exc_info:
            payload["exception"] = mask_text(self.formatException(record.exc_info))
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON formatter on the root logger, replacing handlers.

    Safe to call more than once; OpenFaaS may reuse a warm process.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    """Return a standard library logger; formatting is configured globally."""
    return logging.getLogger(name)
