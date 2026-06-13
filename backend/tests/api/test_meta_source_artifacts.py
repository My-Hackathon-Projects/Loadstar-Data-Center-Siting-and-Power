"""Tests for `/meta/source-artifacts`.

The endpoint reads the SQLite metadata DB written by the pipeline CLIs. We
override the DB path via `SOURCE_ARTIFACTS_DB` and clear the Settings cache so
the service re-reads it on each request.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.core.config import get_settings
from backend.api.main import app

# Mirror the schema written by `backend/pipeline/artifacts.py`.
_CREATE_TABLE = """
CREATE TABLE source_artifacts (
    artifact_name TEXT NOT NULL,
    country_scope TEXT NOT NULL,
    artifact_version TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_status TEXT NOT NULL,
    status TEXT NOT NULL,
    checksum_sha256 TEXT NOT NULL,
    artifact_path TEXT NOT NULL,
    record_count INTEGER NOT NULL,
    fallback TEXT,
    generated_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    PRIMARY KEY (artifact_name, country_scope)
)
"""

_INSERT = """
INSERT INTO source_artifacts (
    artifact_name, country_scope, artifact_version, source_name,
    source_status, status, checksum_sha256, artifact_path, record_count,
    fallback, generated_at, metadata_json
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def _seed_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute(_CREATE_TABLE)
        connection.execute(
            _INSERT,
            (
                "hourly_carbon_subset",
                "SE,DE,IE",
                "hourly-carbon-v1",
                "Ember monthly carbon",
                "fallback",
                "fallback_processed",
                "a" * 64,
                "data/processed/subset/hourly_carbon_subset.json",
                26280,
                "Repeated monthly Ember carbon intensity across each hour.",
                "2026-06-13T05:00:00+00:00",
                json.dumps({"notes": "demo seed"}),
            ),
        )
        connection.execute(
            _INSERT,
            (
                "site_features_subset",
                "SE,DE,IE",
                "site-features-v1",
                "Loadstar feature engineering",
                "generated",
                "processed",
                "b" * 64,
                "data/processed/subset/site_features_subset.json",
                10,
                None,
                "2026-06-13T05:00:01+00:00",
                json.dumps({"notes": "demo seed"}),
            ),
        )
        connection.commit()


@pytest.fixture
def client_with_seeded_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Yield a TestClient bound to a Settings instance with a fresh metadata DB."""

    db_path = tmp_path / "source_artifacts.db"
    _seed_database(db_path)
    monkeypatch.setenv("SOURCE_ARTIFACTS_DB", str(db_path))
    get_settings.cache_clear()
    try:
        yield TestClient(app)
    finally:
        get_settings.cache_clear()


def test_source_artifacts_returns_typed_list(client_with_seeded_db: TestClient) -> None:
    response = client_with_seeded_db.get("/meta/source-artifacts")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data_mode"] == "fixture"
    assert payload["artifact_count"] == 2
    assert {a["artifact_name"] for a in payload["artifacts"]} == {
        "hourly_carbon_subset",
        "site_features_subset",
    }
    first = payload["artifacts"][0]
    assert first["artifact_version"]
    assert first["checksum_sha256"]
    assert first["generated_at"]
    assert isinstance(first["metadata"], dict)
    assert payload["data_version"]


def test_source_artifacts_filter_by_artifact_name(client_with_seeded_db: TestClient) -> None:
    response = client_with_seeded_db.get(
        "/meta/source-artifacts",
        params={"artifact_name": "site_features_subset"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["artifact_count"] == 1
    assert payload["artifacts"][0]["artifact_name"] == "site_features_subset"


def test_source_artifacts_filter_by_country(client_with_seeded_db: TestClient) -> None:
    response = client_with_seeded_db.get("/meta/source-artifacts", params={"country": "SE"})
    assert response.status_code == 200
    payload = response.json()
    # Both seeded rows have country_scope `SE,DE,IE`, so the substring match
    # surfaces both.
    assert payload["artifact_count"] == 2


def test_source_artifacts_data_version_changes_when_checksum_changes(
    client_with_seeded_db: TestClient, tmp_path: Path
) -> None:
    first = client_with_seeded_db.get("/meta/source-artifacts").json()
    db_path = tmp_path / "source_artifacts.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE source_artifacts SET checksum_sha256 = ? WHERE artifact_name = ?",
            ("c" * 64, "site_features_subset"),
        )
        connection.commit()
    second = client_with_seeded_db.get("/meta/source-artifacts").json()
    assert first["data_version"] != second["data_version"]


def test_health_returns_extended_metadata() -> None:
    """Existing assertions still pass; new fields are populated."""

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    # Pre-existing contract.
    assert payload["status"] == "ok"
    assert payload["data_mode"] == "fixture"
    assert payload["cache_key"].startswith("health:")
    # New additive fields.
    assert "version" in payload
    assert "uptime_seconds" in payload
    assert payload["uptime_seconds"] >= 0
    assert "dependencies" in payload
    deps = payload["dependencies"]
    assert deps["postgres"]["status"] in {"ok", "unreachable", "disabled"}
    assert deps["redis"]["status"] in {"ok", "unreachable", "disabled"}


def test_meta_source_artifacts_handles_missing_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the metadata DB doesn't exist yet, return an empty list, not 500."""

    monkeypatch.setenv("SOURCE_ARTIFACTS_DB", str(tmp_path / "missing.db"))
    get_settings.cache_clear()
    try:
        client = TestClient(app)
        response = client.get("/meta/source-artifacts")
        assert response.status_code == 200
        payload = response.json()
        assert payload["artifact_count"] == 0
        assert payload["artifacts"] == []
    finally:
        get_settings.cache_clear()
