"""Tests for the async optimizer endpoint.

The async path persists state in `optimization_runs`, so it requires a real
Postgres cluster. Gated on `LOADSTAR_TEST_POSTGRES_URL`: CI sets the env var
to its Postgres service container; local devs can point it at any Postgres
they trust to drop/recreate the four tables.

`BackgroundTasks` runs synchronously inline under FastAPI's `TestClient`, so a
GET right after the 202 already shows the completed state.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.api.core.config import get_settings
from backend.api.main import app
from backend.api.services import optimizer_jobs, result_cache
from backend.db.connection import is_postgres
from backend.db.migrate import apply_schema_url

_POSTGRES_TEST_DSN = os.environ.get("LOADSTAR_TEST_POSTGRES_URL")
_REASON = "Set LOADSTAR_TEST_POSTGRES_URL to run the async optimizer tests."


def _truncate_optimization_runs(database_url: str) -> None:
    """Reset `optimization_runs` so tests start from a known empty state."""

    import psycopg

    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute("TRUNCATE TABLE optimization_runs")
        connection.commit()


@pytest.fixture
def client_with_db(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Yield a TestClient bound to the configured Postgres DSN."""

    if not (_POSTGRES_TEST_DSN and is_postgres(_POSTGRES_TEST_DSN)):
        pytest.skip(_REASON)
    apply_schema_url(_POSTGRES_TEST_DSN)
    _truncate_optimization_runs(_POSTGRES_TEST_DSN)
    monkeypatch.setenv("DATABASE_URL", _POSTGRES_TEST_DSN)
    get_settings.cache_clear()
    result_cache.reset_result_cache_for_tests()
    try:
        yield TestClient(app)
    finally:
        get_settings.cache_clear()
        result_cache.reset_result_cache_for_tests()


def _payload() -> dict[str, object]:
    return {"cell_id": "851f25d7fffffff", "load_mw": 280, "load_profile": "flat_24_7"}


def test_async_endpoint_runs_solve_and_polls_to_completed(client_with_db: TestClient) -> None:
    response = client_with_db.post("/optimize/supply-mix/async", json=_payload())
    assert response.status_code == 202
    accepted = response.json()
    assert accepted["status"] == "pending"
    assert accepted["job_id"]
    assert accepted["status_url"] == f"/optimize/jobs/{accepted['job_id']}"
    assert accepted["cache_key"].startswith("optimize.supply_mix:")

    poll = client_with_db.get(accepted["status_url"])
    assert poll.status_code == 200
    body = poll.json()
    assert body["status"] == "completed"
    assert body["result"] is not None
    assert body["result"]["solver_status"] == "optimal"
    assert body["solve_ms"] is not None and body["solve_ms"] >= 0
    assert body["completed_at"] is not None


def test_async_endpoint_is_idempotent_on_cache_key(client_with_db: TestClient) -> None:
    first = client_with_db.post("/optimize/supply-mix/async", json=_payload()).json()
    second = client_with_db.post("/optimize/supply-mix/async", json=_payload()).json()
    assert first["job_id"] == second["job_id"]
    assert first["cache_key"] == second["cache_key"]


def test_async_endpoint_returns_failed_status_on_solver_error(
    client_with_db: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(_request: Any) -> Any:
        raise RuntimeError("simulated solver crash")

    monkeypatch.setattr(optimizer_jobs, "optimize_site_supply", boom)
    response = client_with_db.post("/optimize/supply-mix/async", json=_payload())
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    poll = client_with_db.get(f"/optimize/jobs/{job_id}")
    assert poll.status_code == 200
    body = poll.json()
    assert body["status"] == "failed"
    assert body["error"]["code"] == "optimization_failed"
    assert "simulated solver crash" in body["error"]["message"]


def test_optimizer_job_status_404_on_unknown_id(client_with_db: TestClient) -> None:
    response = client_with_db.get("/optimize/jobs/does-not-exist")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "optimizer_job_not_found"


def test_async_endpoint_validates_payload_shape(client_with_db: TestClient) -> None:
    response = client_with_db.post(
        "/optimize/supply-mix/async",
        json={"cell_id": "851f25d7fffffff", "load_mw": -1, "load_profile": "flat_24_7"},
    )
    assert response.status_code == 422


def test_async_persists_request_id_for_correlation(client_with_db: TestClient) -> None:
    response = client_with_db.post(
        "/optimize/supply-mix/async",
        headers={"X-Request-ID": "rehearsal-step-10"},
        json=_payload(),
    )
    job_id = response.json()["job_id"]
    poll = client_with_db.get(f"/optimize/jobs/{job_id}")
    body = poll.json()
    assert body["request_id"] == "rehearsal-step-10"


def test_async_row_lands_in_optimization_runs(client_with_db: TestClient) -> None:
    import psycopg

    response = client_with_db.post("/optimize/supply-mix/async", json=_payload())
    job_id = response.json()["job_id"]
    assert _POSTGRES_TEST_DSN is not None
    with psycopg.connect(_POSTGRES_TEST_DSN) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT run_id, status, cache_key FROM optimization_runs WHERE run_id = %s",
            (job_id,),
        )
        row = cursor.fetchone()
    assert row is not None
    assert row[0] == job_id
    assert row[1] == "completed"
    assert row[2].startswith("optimize.supply_mix:")
