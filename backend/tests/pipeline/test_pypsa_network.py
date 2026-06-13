"""Tests for `backend.pipeline.pypsa_network`.

Synthetic 6-bus / 5-line / 1-link CSV fixtures live entirely in this module
so the test stays self-contained. The fixture exercises:

- HV filtering (a 110 kV line that must be dropped at build time)
- Voltage-tier classification (`ehv` >= 380, `hv` 220-380)
- Cross-border detection (DE <-> FR)
- HVDC dashing flag (one entry from the synthetic links file)
- Bus aggregates (`degree`, `connected_capacity_mva`)
- Idempotent re-runs (DB byte equality + GeoJSON SHA equality)
- Nearest-substation overlay correctness + idempotence
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from backend.pipeline.pypsa_network import (
    EHV_THRESHOLD_KV,
    MIN_VOLTAGE_KV,
    Bus,
    Edge,
    _build_geojson_payload,
    _bus_aggregates,
    app,
    overlay_nearest_substation,
    read_buses,
    read_lines,
    read_links,
    run_pypsa_ingestion,
)

# Six buses spanning DE, FR, IE; one sub-HV bus that should be dropped.
BUSES_CSV = """bus_id,voltage,dc,symbol,under_construction,tags,x,y,country,geometry
DE_380_1,380,f,Substation,f,,10.0,52.0,DE,POINT (10.0 52.0)
DE_380_2,380,f,Substation,f,,11.0,51.0,DE,POINT (11.0 51.0)
DE_220_1,220,f,Substation,f,,9.0,53.0,DE,POINT (9.0 53.0)
FR_380_1,380,f,Substation,f,,5.0,49.0,FR,POINT (5.0 49.0)
IE_220_1,220,f,Substation,f,,-7.0,53.5,IE,POINT (-7.0 53.5)
DE_110_1,110,f,Substation,f,,8.0,50.0,DE,POINT (8.0 50.0)
"""

# Five AC lines (one of which is sub-HV and must be filtered out) plus one
# cross-border DE<->FR EHV line. The header is one line in PyPSA-Eur; the
# noqa pragma silences the line-length lint for the literal CSV.
LINES_CSV = (
    "line_id,bus0,bus1,voltage,i_nom,circuits,s_nom,r,x,b,length,underground,"
    "under_construction,type,tags,geometry\n"
    "L_DE_EHV_1,DE_380_1,DE_380_2,380,1.0,1,1500,0,0,0,150000,f,f,,,\n"
    "L_DE_HV_1,DE_220_1,DE_380_1,220,1.0,1,500,0,0,0,120000,f,f,,,\n"
    "L_DE_HV_2,DE_220_1,DE_380_2,220,1.0,1,400,0,0,0,200000,f,f,,,\n"
    "L_DEFR_EHV,DE_380_1,FR_380_1,380,1.0,1,1200,0,0,0,500000,f,f,,,\n"
    "L_DE_SUBHV,DE_110_1,DE_220_1,110,1.0,1,200,0,0,0,90000,f,f,,,\n"
)

# One HVDC link, IE <-> DE.
LINKS_CSV = """link_id,bus0,bus1,voltage,p_nom,length,underground,under_construction,tags,geometry
DC_IE_DE,IE_220_1,DE_380_2,500,2000,1500000,f,f,,
"""

# Tiny site_features_subset.json with one record near DE_380_1, one near IE_220_1.
SITE_FEATURES_PAYLOAD = {
    "artifact_version": "test",
    "records": [
        {
            "cell_id": "test-cell-de",
            "country_code": "DE",
            "region_name": "Test DE",
            "latitude": 52.05,  # ~5.5 km north of DE_380_1 at (10.0, 52.0)
            "longitude": 10.0,
            "resolution": 5,
            "mean_price_eur_mwh": 60.0,
            "price_volatility": 0.1,
            "carbon_intensity_g_kwh": 100.0,
            "congestion_index": 0.3,
            "headroom_mw": 400.0,
            "dist_hv_substation_km": 5.0,
            "dist_fiber_km": 5.0,
            "dist_ixp_km": 50.0,
            "latency_proxy_ms": 5.0,
            "solar_cf": 0.15,
            "wind_cf": 0.4,
            "water_dist_km": 10.0,
            "cooling_degree_proxy": 800.0,
            "buildable_fraction": 0.5,
            "dc_similarity": 0.5,
            "lightgbm_score": 0.7,
            "shap_values": {},
            "exclusion_flag": False,
        },
        {
            "cell_id": "test-cell-ie",
            "country_code": "IE",
            "region_name": "Test IE",
            "latitude": 53.5,  # exactly on IE_220_1
            "longitude": -7.0,
            "resolution": 5,
            "mean_price_eur_mwh": 80.0,
            "price_volatility": 0.1,
            "carbon_intensity_g_kwh": 250.0,
            "congestion_index": 0.5,
            "headroom_mw": 250.0,
            "dist_hv_substation_km": 8.0,
            "dist_fiber_km": 12.0,
            "dist_ixp_km": 30.0,
            "latency_proxy_ms": 8.0,
            "solar_cf": 0.13,
            "wind_cf": 0.45,
            "water_dist_km": 5.0,
            "cooling_degree_proxy": 400.0,
            "buildable_fraction": 0.6,
            "dc_similarity": 0.5,
            "lightgbm_score": 0.6,
            "shap_values": {},
            "exclusion_flag": False,
        },
    ],
}


@pytest.fixture()
def raw_dir(tmp_path: Path) -> Path:
    """Drop the synthetic PyPSA-Eur CSVs into a tmp dir."""

    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "buses.csv").write_text(BUSES_CSV, encoding="utf-8")
    (raw / "lines.csv").write_text(LINES_CSV, encoding="utf-8")
    (raw / "links.csv").write_text(LINKS_CSV, encoding="utf-8")
    return raw


@pytest.fixture()
def site_features_path(tmp_path: Path) -> Path:
    path = tmp_path / "site_features.json"
    path.write_text(
        json.dumps(SITE_FEATURES_PAYLOAD, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def test_read_buses_drops_invalid_rows(raw_dir: Path) -> None:
    buses = read_buses(raw_dir / "buses.csv")
    assert len(buses) == 6
    assert {b.bus_id for b in buses} == {
        "DE_380_1",
        "DE_380_2",
        "DE_220_1",
        "FR_380_1",
        "IE_220_1",
        "DE_110_1",
    }


def test_read_lines_converts_meters_to_km(raw_dir: Path) -> None:
    edges = read_lines(raw_dir / "lines.csv")
    by_id = {e.edge_id: e for e in edges}
    # 150_000 metres → 150.0 km
    assert by_id["L_DE_EHV_1"].length_km == pytest.approx(150.0)
    assert by_id["L_DEFR_EHV"].length_km == pytest.approx(500.0)
    # is_hvdc is False for AC lines
    assert all(not e.is_hvdc for e in edges)


def test_read_links_marks_hvdc(raw_dir: Path) -> None:
    edges = read_links(raw_dir / "links.csv")
    assert len(edges) == 1
    assert edges[0].is_hvdc is True
    assert edges[0].edge_id == "link:DC_IE_DE"
    assert edges[0].length_km == pytest.approx(1500.0)


def test_geojson_drops_sub_hv(raw_dir: Path) -> None:
    buses = read_buses(raw_dir / "buses.csv")
    edges = [*read_lines(raw_dir / "lines.csv"), *read_links(raw_dir / "links.csv")]
    payload = _build_geojson_payload(buses, edges)
    voltages = {f["properties"]["voltage_kv"] for f in payload["features"]}
    assert all(v >= MIN_VOLTAGE_KV for v in voltages)
    # The 110 kV bus and the L_DE_SUBHV line must not appear.
    feature_ids = {f["id"] for f in payload["features"]}
    assert "bus:DE_110_1" not in feature_ids
    assert "line:L_DE_SUBHV" not in feature_ids


def test_geojson_voltage_tiers_assigned(raw_dir: Path) -> None:
    buses = read_buses(raw_dir / "buses.csv")
    edges = [*read_lines(raw_dir / "lines.csv"), *read_links(raw_dir / "links.csv")]
    payload = _build_geojson_payload(buses, edges)
    line_features = [f for f in payload["features"] if f["properties"]["kind"] == "line"]
    for feature in line_features:
        props = feature["properties"]
        expected = "ehv" if props["voltage_kv"] >= EHV_THRESHOLD_KV else "hv"
        assert props["voltage_tier"] == expected


def test_geojson_marks_cross_border_and_hvdc(raw_dir: Path) -> None:
    buses = read_buses(raw_dir / "buses.csv")
    edges = [*read_lines(raw_dir / "lines.csv"), *read_links(raw_dir / "links.csv")]
    payload = _build_geojson_payload(buses, edges)
    by_id = {f["id"]: f for f in payload["features"]}
    cross_border = by_id["line:L_DEFR_EHV"]["properties"]
    assert cross_border["is_cross_border"] is True
    assert {cross_border["country0"], cross_border["country1"]} == {"DE", "FR"}
    hvdc = by_id["line:link:DC_IE_DE"]["properties"]
    assert hvdc["is_hvdc"] is True
    assert hvdc["is_cross_border"] is True


def test_bus_aggregates_match_hand_count(raw_dir: Path) -> None:
    buses = read_buses(raw_dir / "buses.csv")
    edges = [*read_lines(raw_dir / "lines.csv"), *read_links(raw_dir / "links.csv")]
    hv_buses = {b.bus_id: b for b in buses if b.voltage_kv >= MIN_VOLTAGE_KV}
    aggregates = _bus_aggregates(edges, hv_buses)
    # DE_380_1 incident edges: L_DE_EHV_1, L_DE_HV_1, L_DEFR_EHV → degree 3,
    # capacity 1500 + 500 + 1200 = 3200.
    degree, capacity = aggregates["DE_380_1"]
    assert degree == 3
    assert capacity == pytest.approx(3200.0)
    # IE_220_1 is reached only via the HVDC link → degree 1, capacity 2000.
    degree_ie, capacity_ie = aggregates["IE_220_1"]
    assert degree_ie == 1
    assert capacity_ie == pytest.approx(2000.0)


def test_run_pypsa_ingestion_idempotent(
    raw_dir: Path, site_features_path: Path, tmp_path: Path
) -> None:
    db_path = tmp_path / "grid.db"
    geojson_path = tmp_path / "transmission_grid.geojson"
    metadata_db = tmp_path / "metadata.db"

    first = run_pypsa_ingestion(
        raw_dir=raw_dir,
        database=db_path,
        geojson_out=geojson_path,
        site_features=site_features_path,
        metadata_database=metadata_db,
    )
    assert first.rendered_bus_count > 0
    assert first.rendered_edge_count > 0
    geojson_sha_1 = hashlib.sha256(geojson_path.read_bytes()).hexdigest()
    sites_sha_1 = hashlib.sha256(site_features_path.read_bytes()).hexdigest()

    second = run_pypsa_ingestion(
        raw_dir=raw_dir,
        database=db_path,
        geojson_out=geojson_path,
        site_features=site_features_path,
        metadata_database=metadata_db,
    )
    assert second.rendered_bus_count == first.rendered_bus_count
    assert second.rendered_edge_count == first.rendered_edge_count
    assert hashlib.sha256(geojson_path.read_bytes()).hexdigest() == geojson_sha_1
    assert hashlib.sha256(site_features_path.read_bytes()).hexdigest() == sites_sha_1


def test_run_pypsa_ingestion_writes_db_tables(
    raw_dir: Path, site_features_path: Path, tmp_path: Path
) -> None:
    db_path = tmp_path / "grid.db"
    geojson_path = tmp_path / "transmission_grid.geojson"
    metadata_db = tmp_path / "metadata.db"

    run_pypsa_ingestion(
        raw_dir=raw_dir,
        database=db_path,
        geojson_out=geojson_path,
        site_features=site_features_path,
        metadata_database=metadata_db,
    )
    with sqlite3.connect(db_path) as conn:
        bus_rows = conn.execute("SELECT bus_id, voltage_kv FROM pypsa_bus").fetchall()
        line_rows = conn.execute("SELECT edge_id, voltage_kv, is_hvdc FROM pypsa_line").fetchall()
        meta_rows = dict(conn.execute("SELECT key, value FROM meta").fetchall())

    assert all(v >= MIN_VOLTAGE_KV for _, v in bus_rows)
    assert "DE_110_1" not in {row[0] for row in bus_rows}
    line_ids = {row[0] for row in line_rows}
    assert "L_DE_SUBHV" not in line_ids
    assert "link:DC_IE_DE" in line_ids
    assert int(meta_rows["rendered_bus_count"]) == len(bus_rows)
    assert "sha256:buses.csv" in meta_rows


def test_overlay_writes_three_keys(raw_dir: Path, site_features_path: Path) -> None:
    buses = read_buses(raw_dir / "buses.csv")
    edges = [*read_lines(raw_dir / "lines.csv"), *read_links(raw_dir / "links.csv")]
    updated = overlay_nearest_substation(site_features_path, buses, edges)
    assert updated == 2

    payload = json.loads(site_features_path.read_text(encoding="utf-8"))
    de_record = next(r for r in payload["records"] if r["cell_id"] == "test-cell-de")
    ie_record = next(r for r in payload["records"] if r["cell_id"] == "test-cell-ie")

    # DE site is ~5.5 km north of DE_380_1; nearest must be that bus at 380 kV.
    assert de_record["nearest_substation_kv"] == 380.0
    assert 4.0 < de_record["nearest_substation_distance_km"] < 8.0
    # IE site is exactly on IE_220_1; distance ~0.
    assert ie_record["nearest_substation_kv"] == 220.0
    assert ie_record["nearest_substation_distance_km"] < 0.5


def test_overlay_idempotent(raw_dir: Path, site_features_path: Path) -> None:
    buses = read_buses(raw_dir / "buses.csv")
    edges = [*read_lines(raw_dir / "lines.csv"), *read_links(raw_dir / "links.csv")]
    overlay_nearest_substation(site_features_path, buses, edges)
    sha_before = hashlib.sha256(site_features_path.read_bytes()).hexdigest()
    overlay_nearest_substation(site_features_path, buses, edges)
    sha_after = hashlib.sha256(site_features_path.read_bytes()).hexdigest()
    assert sha_before == sha_after


def test_cli_smoke(raw_dir: Path, site_features_path: Path, tmp_path: Path) -> None:
    db_path = tmp_path / "grid.db"
    geojson_path = tmp_path / "transmission_grid.geojson"
    metadata_db = tmp_path / "metadata.db"

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "--raw-dir",
            str(raw_dir),
            "--database",
            str(db_path),
            "--geojson-out",
            str(geojson_path),
            "--site-features",
            str(site_features_path),
            "--metadata-database",
            str(metadata_db),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Wrote" in result.output
    assert geojson_path.exists()
    assert db_path.exists()


def test_cli_skip_overlay(raw_dir: Path, site_features_path: Path, tmp_path: Path) -> None:
    """``--skip-overlay`` builds the GeoJSON but leaves site features alone."""

    db_path = tmp_path / "grid.db"
    geojson_path = tmp_path / "transmission_grid.geojson"
    metadata_db = tmp_path / "metadata.db"
    sha_before = hashlib.sha256(site_features_path.read_bytes()).hexdigest()

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "--raw-dir",
            str(raw_dir),
            "--database",
            str(db_path),
            "--geojson-out",
            str(geojson_path),
            "--site-features",
            str(site_features_path),
            "--metadata-database",
            str(metadata_db),
            "--skip-overlay",
        ],
    )
    assert result.exit_code == 0
    assert geojson_path.exists()
    sha_after = hashlib.sha256(site_features_path.read_bytes()).hexdigest()
    assert sha_after == sha_before


def test_missing_csv_raises(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        run_pypsa_ingestion(
            raw_dir=empty,
            database=tmp_path / "grid.db",
            geojson_out=tmp_path / "g.geojson",
            site_features=None,
            metadata_database=tmp_path / "metadata.db",
        )


def test_islanded_hv_buses_dropped() -> None:
    """A bus with no incident HV edge must not appear in the GeoJSON."""

    buses = [
        Bus("ISO_220", 220.0, "DE", 10.0, 50.0, dc=False),
        Bus("CONN_380_A", 380.0, "DE", 11.0, 51.0, dc=False),
        Bus("CONN_380_B", 380.0, "DE", 12.0, 52.0, dc=False),
    ]
    edges = [
        Edge("E1", "CONN_380_A", "CONN_380_B", 380.0, 1500.0, 100.0, is_hvdc=False),
    ]
    payload = _build_geojson_payload(buses, edges)
    bus_ids = {f["id"] for f in payload["features"] if f["properties"]["kind"] == "bus"}
    assert "bus:ISO_220" not in bus_ids
    assert {"bus:CONN_380_A", "bus:CONN_380_B"}.issubset(bus_ids)
