"""Application logging configuration.

Two output modes:

- `json` (default): one JSON object per log record, with `timestamp`, `level`,
  `logger`, `request_id`, `message`, and any structured `extra` fields. This is
  the format intended for log aggregators in production.
- `text`: human-readable single-line records, useful while watching the demo
  in a terminal. Selected via `LOG_FORMAT=text` in `.env`.

Every record carries the active request ID via the `RequestIdFilter`, which
reads the contextvar set by `middleware/request_id.py`. Records emitted
outside a request (startup, pipeline CLIs) carry `request_id="-"`.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from backend.api.middleware.request_id import get_request_id

# Stdlib `LogRecord` attributes that we never want to copy into the JSON payload
# as `extra` fields (they are already represented or not useful).
_RESERVED_ATTRS: frozenset[str] = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "request_id",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }
)


class RequestIdFilter(logging.Filter):
    """Inject the active request ID into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class JsonFormatter(logging.Formatter):
    """Render log records as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": time.strftime(
                "%Y-%m-%dT%H:%M:%S",
                time.gmtime(record.created),
            )
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Surface arbitrary keyword extras passed via `logger.info(..., extra={...})`.
        for key, value in record.__dict__.items():
            if key in _RESERVED_ATTRS or key.startswith("_"):
                continue
            payload[key] = value
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level_name: str, log_format: str = "json") -> None:
    """Configure process logging for the API and pipeline CLIs.

    Idempotent: replaces any existing handlers on the root logger, so repeated
    calls (e.g. in tests) leave a single handler with the configured format.
    """

    level = getattr(logging, level_name.upper(), logging.INFO)
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    if log_format == "text":
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s [%(request_id)s] %(name)s %(message)s",
            )
        )
    else:
        handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)
