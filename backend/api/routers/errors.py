"""Shared HTTP error helpers for API routers."""

from fastapi import HTTPException

from backend.engine.contracts import ApiErrorDetail


def key_error_message(exc: KeyError) -> str:
    """Return a clean message from a service-layer KeyError."""

    if exc.args:
        return str(exc.args[0])
    return "Resource not found."


def not_found(message: str, *, code: str) -> HTTPException:
    """Build a structured 404 response."""

    return HTTPException(
        status_code=404,
        detail=ApiErrorDetail(code=code, message=message).model_dump(),
    )


def unprocessable(message: str, *, code: str) -> HTTPException:
    """Build a structured 422 response."""

    return HTTPException(
        status_code=422,
        detail=ApiErrorDetail(code=code, message=message).model_dump(),
    )
