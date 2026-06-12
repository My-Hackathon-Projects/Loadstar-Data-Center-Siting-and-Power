import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from backend.pipeline.subset_ingestion import parse_countries, run_subset_ingestion


def test_parse_countries_normalizes_and_deduplicates() -> None:
    assert parse_countries("se, DE,ie,se") == ("SE", "DE", "IE")


def test_parse_countries_rejects_invalid_codes() -> None:
    with pytest.raises(ValueError, match="Invalid country code"):
        parse_countries("SE,Germany")


def test_subset_ingestion_writes_required_issue_6_artifacts(tmp_path: Path) -> None:
    result = run_subset_ingestion(
        countries="SE,DE",
        output_dir=tmp_path / "processed",
        metadata_database=tmp_path / "source_artifacts.db",
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["countries"] == ["SE", "DE"]
    artifact_names = {artifact["name"] for artifact in manifest["artifacts"]}
    assert artifact_names == {
        "pypsa_network_subset",
        "pypsa_clustered_opf",
        "hourly_energy_subset",
        "ember_grids_congestion_layers",
        "osm_site_feature_layers",
        "connectivity_fiber_or_ixp",
    }

    for artifact in manifest["artifacts"]:
        path = result.output_dir / artifact["path"].split("/")[-1]
        payload = json.loads(path.read_text(encoding="utf-8"))
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        assert set(payload["countries"]) == {"SE", "DE"}
        assert payload["artifact_version"] == "subset-fixture-proxy-v1"
        assert payload["records"]
        assert artifact["checksum_sha256"] == checksum


def test_subset_ingestion_records_precomputed_non_live_opf(tmp_path: Path) -> None:
    result = run_subset_ingestion(
        countries="SE,DE,IE",
        output_dir=tmp_path / "processed",
        metadata_database=tmp_path / "source_artifacts.db",
    )

    opf_summary = next(
        artifact for artifact in result.artifacts if artifact.name == "pypsa_clustered_opf"
    )
    opf_payload = json.loads((result.output_dir / "pypsa_clustered_opf.json").read_text())
    opf_record = opf_payload["records"][0]
    assert opf_summary.status == "precomputed_stub"
    assert opf_record["solver"]["live_solve"] is False
    assert opf_record["line_loadings"]
    assert opf_record["nodal_prices"]


def test_source_artifacts_rows_are_upserted_idempotently(tmp_path: Path) -> None:
    database_path = tmp_path / "source_artifacts.db"

    run_subset_ingestion(
        countries="SE,DE,IE",
        output_dir=tmp_path / "processed",
        metadata_database=database_path,
    )
    run_subset_ingestion(
        countries="SE,DE,IE",
        output_dir=tmp_path / "processed",
        metadata_database=database_path,
    )

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT artifact_name, checksum_sha256
            FROM source_artifacts
            WHERE country_scope = 'SE,DE,IE'
            ORDER BY artifact_name
            """
        ).fetchall()

    assert len(rows) == 7
    assert {row[0] for row in rows} >= {
        "subset_ingestion_manifest",
        "pypsa_network_subset",
        "pypsa_clustered_opf",
    }
    assert all(len(row[1]) == 64 for row in rows)
