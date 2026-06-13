"""Tests for the JSON log formatter and request-ID filter."""

from __future__ import annotations

import io
import json
import logging

from backend.api.core.logging import JsonFormatter, RequestIdFilter, configure_logging
from backend.api.middleware.request_id import _request_id


def test_json_formatter_emits_required_keys() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="loadstar.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    record.request_id = "abc123"
    payload = json.loads(formatter.format(record))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "loadstar.test"
    assert payload["request_id"] == "abc123"
    assert payload["message"] == "hello world"
    assert "timestamp" in payload


def test_json_formatter_includes_extra_fields() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="loadstar.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="optimize.solved",
        args=(),
        exc_info=None,
    )
    record.request_id = "abc123"
    record.cell_id = "851f25d7fffffff"
    record.solve_ms = 12.5
    payload = json.loads(formatter.format(record))
    assert payload["cell_id"] == "851f25d7fffffff"
    assert payload["solve_ms"] == 12.5


def test_request_id_filter_pulls_from_contextvar() -> None:
    filter_ = RequestIdFilter()
    record = logging.LogRecord(
        name="loadstar.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="msg",
        args=(),
        exc_info=None,
    )
    token = _request_id.set("ctx-id-9")
    try:
        assert filter_.filter(record) is True
        assert record.request_id == "ctx-id-9"
    finally:
        _request_id.reset(token)


def test_configure_logging_replaces_handlers_and_writes_json() -> None:
    configure_logging("INFO", "json")
    root = logging.getLogger()
    assert len(root.handlers) == 1
    handler = root.handlers[0]
    buffer = io.StringIO()
    handler.stream = buffer  # type: ignore[attr-defined]
    logging.getLogger("loadstar.test").info("structured log")
    output = buffer.getvalue().strip()
    payload = json.loads(output)
    assert payload["message"] == "structured log"
    assert payload["request_id"] == "-"


def test_configure_logging_text_mode_is_human_readable() -> None:
    configure_logging("INFO", "text")
    root = logging.getLogger()
    handler = root.handlers[0]
    buffer = io.StringIO()
    handler.stream = buffer  # type: ignore[attr-defined]
    logging.getLogger("loadstar.test").info("plain text")
    output = buffer.getvalue().strip()
    assert "plain text" in output
    # Restore JSON for the rest of the suite (other tests assume JSON).
    configure_logging("INFO", "json")
