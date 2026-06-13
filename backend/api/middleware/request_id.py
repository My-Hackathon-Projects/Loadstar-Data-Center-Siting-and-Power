"""Request-ID middleware.

Reads inbound `X-Request-ID`, falls back to a generated UUID, stores the value
in a module-level `ContextVar` so log records and downstream services can pick
it up without threading it through every signature, and echoes it on the
response. Other modules access the current request ID via `get_request_id()`.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# 128-byte cap on inbound IDs blocks accidentally-huge headers from upstream
# proxies. The default `"-"` is what gets stamped on log records emitted before
# any request hits the middleware (e.g. uvicorn startup messages).
_MAX_INBOUND_LENGTH = 128
_HEADER_NAME = "X-Request-ID"

_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    """Return the request ID for the active request, or `"-"` outside a request."""

    return _request_id.get()


def _generate_request_id() -> str:
    return uuid.uuid4().hex


def _coerce_inbound(value: str | None) -> str:
    if not value or len(value) > _MAX_INBOUND_LENGTH:
        return _generate_request_id()
    return value


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Stamp every request and response with a correlation ID."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = _coerce_inbound(request.headers.get(_HEADER_NAME))
        token = _request_id.set(request_id)
        try:
            response = await call_next(request)
        finally:
            _request_id.reset(token)
        response.headers[_HEADER_NAME] = request_id
        return response
