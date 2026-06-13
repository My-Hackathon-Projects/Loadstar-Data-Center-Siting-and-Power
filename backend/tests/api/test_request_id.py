"""Tests for the request-ID middleware."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from backend.api.main import app

_HEX_RE = re.compile(r"^[0-9a-f]{32}$")


def test_request_id_header_is_generated_when_missing() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    request_id = response.headers["X-Request-ID"]
    assert _HEX_RE.match(request_id), f"expected uuid hex, got {request_id!r}"


def test_request_id_header_is_echoed_when_provided() -> None:
    client = TestClient(app)
    response = client.get("/health", headers={"X-Request-ID": "demo-rehearsal-123"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "demo-rehearsal-123"


def test_request_id_too_long_is_replaced() -> None:
    client = TestClient(app)
    oversized = "x" * 500
    response = client.get("/health", headers={"X-Request-ID": oversized})
    assert response.status_code == 200
    request_id = response.headers["X-Request-ID"]
    assert request_id != oversized
    assert _HEX_RE.match(request_id)


def test_two_requests_get_distinct_ids() -> None:
    client = TestClient(app)
    first = client.get("/health").headers["X-Request-ID"]
    second = client.get("/health").headers["X-Request-ID"]
    assert first != second
