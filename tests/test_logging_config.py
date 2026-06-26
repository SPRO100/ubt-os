"""Unit-тесты для structured JSON logging и correlation ID."""
import json
import logging

from ubt_os.core.logging_config import (
    JsonFormatter,
    set_request_id,
    get_request_id,
    _request_id_var,
)


def _make_record(msg: str, level: int = logging.INFO, extra: dict | None = None) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test.logger", level=level, pathname="", lineno=0,
        msg=msg, args=(), exc_info=None,
    )
    if extra:
        for k, v in extra.items():
            setattr(record, k, v)
    return record


def test_json_output_is_valid():
    fmt = JsonFormatter()
    record = _make_record("hello world")
    output = fmt.format(record)
    data = json.loads(output)
    assert data["msg"] == "hello world"
    assert data["level"] == "INFO"
    assert data["logger"] == "test.logger"
    assert "ts" in data


def test_request_id_in_output():
    token = _request_id_var.set("test-req-42")
    try:
        fmt = JsonFormatter()
        record = _make_record("with request id")
        data = json.loads(fmt.format(record))
        assert data["request_id"] == "test-req-42"
    finally:
        _request_id_var.reset(token)


def test_no_request_id_when_not_set():
    token = _request_id_var.set(None)
    try:
        fmt = JsonFormatter()
        record = _make_record("no id")
        data = json.loads(fmt.format(record))
        assert "request_id" not in data
    finally:
        _request_id_var.reset(token)


def test_extra_fields_included():
    fmt = JsonFormatter()
    record = _make_record("with extra", extra={"account_id": "acc123", "vertical": "nutra"})
    data = json.loads(fmt.format(record))
    assert data["account_id"] == "acc123"
    assert data["vertical"] == "nutra"


def test_exception_included():
    fmt = JsonFormatter()
    try:
        raise ValueError("test error")
    except ValueError:
        import sys
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="", lineno=0,
            msg="error occurred", args=(), exc_info=sys.exc_info(),
        )
        data = json.loads(fmt.format(record))
        assert "exc" in data
        assert "ValueError" in data["exc"]


def test_set_get_request_id():
    token = _request_id_var.set(None)
    try:
        assert get_request_id() is None
        set_request_id("req-abc")
        assert get_request_id() == "req-abc"
    finally:
        _request_id_var.reset(token)
