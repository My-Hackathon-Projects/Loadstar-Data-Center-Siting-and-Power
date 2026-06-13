"""Tests for `backend.pipeline.hourly_price`.

The CLI prefers the local Ember SQLite ledger (the output of
`ember/ingest.py`) and falls back to a flat fixture broadcast when the DB
is missing. Both paths must produce the same artifact schema and the same
`source_artifacts.db` row contract that downstream consumers expect.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from backend.pipeline.hourly_price import run_hourly_price_ingestion


def _write_minimal_ember_db(path: Path) -> None:
    """Build the smallest Ember-shaped SQLite the CLI can consume.

    Mirrors the `ember/ingest.py` schema exactly. We only populate the
    subset of columns the CLI reads, plus a 24-hour shape per zone.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE ember_price_profile (
                zone_id TEXT NOT NULL,
                iso3_code TEXT NOT NULL,
                sample_year INTEGER NOT NULL,
                mean_price_eur_mwh REAL NOT NULL,
                price_volatility REAL NOT NULL,
                sample_hours INTEGER NOT NULL,
                PRIMARY KEY (zone_id, sample_year)
            );
            CREATE TABLE ember_price_hourly_shape (
                zone_id TEXT NOT NULL,
                sample_year INTEGER NOT NULL,
                hour INTEGER NOT NULL,
                shape_multiplier REAL NOT NULL,
                hour_mean_price_eur_mwh REAL NOT NULL,
                PRIMARY KEY (zone_id, sample_year, hour)
            );
            """
        )
        connection.execute(
            """
            INSERT INTO ember_price_profile
              (zone_id, iso3_code, sample_year, mean_price_eur_mwh, price_volatility, sample_hours)
              VALUES ('SE', 'SWE', 2025, 42.64, 38.24, 8760)
            """
        )
        connection.executemany(
            """
            INSERT INTO ember_price_hourly_shape
              (zone_id, sample_year, hour, shape_multiplier, hour_mean_price_eur_mwh)
              VALUES (?, ?, ?, ?, ?)
            """,
            [("SE", 2025, hour, 1.0, 42.64) for hour in range(24)],
        )
        connection.commit()


def test_hourly_price_prefers_ember_when_db_present(tmp_path: Path) -> None:
    """When ember_prices.db exists, the artifact carries real Ember values."""

    ember_db = tmp_path / "ember" / "dataset" / "ember_prices.db"
    _write_minimal_ember_db(ember_db)

    result = run_hourly_price_ingestion(
        countries="SE",
        output_dir=tmp_path / "processed",
        metadata_database=tmp_path / "source_artifacts.db",
        ember_db_path=ember_db,
    )

    payload = json.loads(result.output_path.read_text(encoding="utf-8"))
    assert payload["active_method"] == "ember_csv_local_db"
    assert payload["records"][0]["zone_id"] == "SE"
    assert payload["records"][0]["mean_price_eur_mwh"] == 42.64
    assert payload["records"][0]["sample_year"] == 2025
    assert len(payload["records"][0]["hour_shape"]) == 24

    with sqlite3.connect(result.metadata_database) as connection:
        row = connection.execute(
            """
            SELECT artifact_name, source_status
              FROM source_artifacts
              WHERE artifact_name = 'hourly_price_subset'
            """,
        ).fetchone()
    assert row == ("hourly_price_subset", "preferred")


def test_hourly_price_falls_back_when_db_missing(tmp_path: Path) -> None:
    """No DB on disk ⇒ flat fixture broadcast, recorded as fallback."""

    result = run_hourly_price_ingestion(
        countries="SE,DE,IE",
        output_dir=tmp_path / "processed",
        metadata_database=tmp_path / "source_artifacts.db",
        ember_db_path=tmp_path / "nope.db",  # intentionally missing
    )

    payload = json.loads(result.output_path.read_text(encoding="utf-8"))
    assert payload["active_method"] == "fixture_static_price"
    assert {record["zone_id"] for record in payload["records"]} == {"SE", "DE", "IE"}
    # Fallback shape is intentionally flat — no synthetic curve.
    for record in payload["records"]:
        assert record["hour_shape"] == [1.0] * 24
        assert record["sample_year"] is None

    with sqlite3.connect(result.metadata_database) as connection:
        row = connection.execute(
            """
            SELECT source_status
              FROM source_artifacts
              WHERE artifact_name = 'hourly_price_subset'
            """,
        ).fetchone()
    assert row == ("fallback",)


def test_hourly_price_method_ember_requires_db(tmp_path: Path) -> None:
    """`--method ember` must error when the DB is missing, not silently fall back."""

    with pytest.raises(ValueError, match="does not exist"):
        run_hourly_price_ingestion(
            countries="SE",
            output_dir=tmp_path / "processed",
            metadata_database=tmp_path / "source_artifacts.db",
            ember_db_path=tmp_path / "missing.db",
            method="ember",
        )


def test_hourly_price_method_fixture_skips_ember_db(tmp_path: Path) -> None:
    """`--method fixture` ignores even a present DB — useful for tests/demos."""

    ember_db = tmp_path / "ember" / "dataset" / "ember_prices.db"
    _write_minimal_ember_db(ember_db)

    result = run_hourly_price_ingestion(
        countries="SE",
        output_dir=tmp_path / "processed",
        metadata_database=tmp_path / "source_artifacts.db",
        ember_db_path=ember_db,
        method="fixture",
    )

    payload = json.loads(result.output_path.read_text(encoding="utf-8"))
    assert payload["active_method"] == "fixture_static_price"
