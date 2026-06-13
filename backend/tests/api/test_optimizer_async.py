"""Tests for the async optimizer endpoint.

`BackgroundTasks` runs synchronously inline under FastAPI's `TestClient`, so a
GET right after the 202 already shows the completed state. We seed a temp
SQLite DB for the test, point Settings at it via the env var, and apply the
migrations.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.core.config import get_settings
from backend.api.main import app
from backend.api.services import optimizer_jobs, result_cache
from backend.db.migrate import apply_schema


@pytest.fixture
def client_with_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Yield a TestClient bound to a freshly migrated SQLite database."""

    db_path = tmp_path / "loadstar.db"
    apply_schema(db_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.resolve()}")
    get_settings.cache_clear()
    result_cache.reset_result_cache_for_tests()
    yield TestClient(app)
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

    # BackgroundTasks runs inline under TestClient, so the row is already in
    # its terminal state by the time we poll.
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
    def boom(_request: object) -> object:
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
    # One of the two requests carried the explicit id; the row stores the
    # enqueue request's id so logs and DB rows can be correlated.
    assert body["request_id"] == "rehearsal-step-10"


def test_async_row_lands_in_optimization_runs(client_with_db: TestClient, tmp_path: Path) -> None:
    response = client_with_db.post("/optimize/supply-mix/async", json=_payload())
    job_id = response.json()["job_id"]
    db_path = tmp_path / "loadstar.db"
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT run_id, status, cache_key FROM optimization_runs WHERE run_id = ?",
            (job_id,),
        ).fetchone()
    assert row is not None
    assert row[0] == job_id
    assert row[1] == "completed"
    assert row[2].startswith("optimize.supply_mix:")
