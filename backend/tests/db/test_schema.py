"""Schema migration tests.

The Loadstar API uses Postgres only. These tests apply the migrations against
a live Postgres cluster pointed at by `LOADSTAR_TEST_POSTGRES_URL`. CI sets
the env var to its Postgres service container; local devs can point it at any
Postgres they trust to drop and recreate four tables.

Tests are skipped when no Postgres URL is configured so `pytest` can run on
machines without a Postgres install.
"""

from __future__ import annotations

import os

import pytest

from backend.db.connection import is_postgres
from backend.db.migrate import apply_schema_url

_POSTGRES_TEST_DSN = os.environ.get("LOADSTAR_TEST_POSTGRES_URL")
_REASON = "Set LOADSTAR_TEST_POSTGRES_URL to run the Postgres schema tests."


@pytest.mark.skipif(
    not (_POSTGRES_TEST_DSN and is_postgres(_POSTGRES_TEST_DSN)),
    reason=_REASON,
)
def test_postgres_schema_applies_cleanly() -> None:
    """Apply the migrations against a real cluster and confirm the four tables exist."""

    import psycopg

    assert _POSTGRES_TEST_DSN is not None  # mypy/pyright narrowing for the skip guard.
    apply_schema_url(_POSTGRES_TEST_DSN)
    with psycopg.connect(_POSTGRES_TEST_DSN) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
            """
        )
        rows = cursor.fetchall()
    table_names = [row[0] for row in rows]
    assert {"h3_cells", "hourly_energy", "optimization_runs", "site_features"} <= set(
        table_names
    )


@pytest.mark.skipif(
    not (_POSTGRES_TEST_DSN and is_postgres(_POSTGRES_TEST_DSN)),
    reason=_REASON,
)
def test_postgres_schema_includes_optimization_runs_status_columns() -> None:
    """The 003 migration adds job-state columns; assert they all land."""

    import psycopg

    assert _POSTGRES_TEST_DSN is not None
    apply_schema_url(_POSTGRES_TEST_DSN)
    with psycopg.connect(_POSTGRES_TEST_DSN) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'optimization_runs'
            ORDER BY column_name
            """
        )
        columns = {row[0] for row in cursor.fetchall()}
    expected = {
        "run_id",
        "cell_id",
        "load_mw",
        "request_json",
        "result_json",
        "cache_key",
        "created_at",
        "status",
        "started_at",
        "completed_at",
        "error_message",
        "solve_ms",
        "request_id",
    }
    assert expected <= columns
