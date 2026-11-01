import json
import logging
import sys
from typing import Any

from common.log import JsonFormatter, configure_logging, get_logger
from common.tenant import RequestContext, bind_context


def _format(record: logging.LogRecord) -> dict[str, Any]:
    out: dict[str, Any] = json.loads(JsonFormatter().format(record))
    return out


def _record(msg: str, **extra) -> logging.LogRecord:
    record = logging.makeLogRecord({"msg": msg, "levelname": "INFO", "name": "t"})
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_context_fields_are_attached():
    ctx = RequestContext(tenant_id="uni-a", document_id="doc-1", correlation_id="c1")
    with bind_context(ctx):
        out = _format(_record("stored"))
    assert out["tenant_id"] == "uni-a"
    assert out["document_id"] == "doc-1"
    assert out["correlation_id"] == "c1"
    assert out["message"] == "stored"


def test_message_and_extra_are_masked():
    out = _format(_record("bad cnic 35202-1234567-3", full_name="Ayesha Siddiqui", step="extract"))
    assert "1234567" not in out["message"]
    assert out["full_name"] == "A***(15)"
    assert out["step"] == "extract"


def test_exception_text_is_masked():
    try:
        raise ValueError("cnic 35202-1234567-3 invalid")
    except ValueError:
        logger = get_logger("t")
        record = logger.makeRecord("t", logging.ERROR, __file__, 1, "failed", (), None)
        record.exc_info = sys.exc_info()
    out = _format(record)
    assert "1234567" not in out["exception"]


def test_configure_logging_is_idempotent():
    configure_logging("debug")
    configure_logging("info")
    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, JsonFormatter)
    assert root.level == logging.INFO
