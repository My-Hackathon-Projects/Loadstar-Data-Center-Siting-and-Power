import json
import sqlite3
from pathlib import Path

from backend.engine.contracts import SiteFeature
from backend.engine.fixtures import FEATURE_COLLECTION
from backend.pipeline.alphaearth_land import run_alphaearth_land_model
from backend.pipeline.feature_engineering import run_feature_engineering
from backend.pipeline.hourly_carbon import run_hourly_carbon_ingestion
from backend.pipeline.hourly_price import run_hourly_price_ingestion
from backend.pipeline.subset_ingestion import run_subset_ingestion

# Cells the SE,DE,IE subset pipeline should produce, derived from the dataset so
# the assertion survives the collection growing.
_SUBSET_CELL_COUNT = sum(1 for s in FEATURE_COLLECTION if s.country_code in {"SE", "DE", "IE"})


def test_feature_engineering_outputs_complete_subset_features(tmp_path: Path) -> None:
    output_dir = tmp_path / "processed"
    metadata_database = tmp_path / "source_artifacts.db"
    run_subset_ingestion(
        countries="SE,DE,IE",
        output_dir=output_dir,
        metadata_database=metadata_database,
    )
    run_hourly_carbon_ingestion(
        countries="SE,DE,IE",
        output_dir=output_dir,
        metadata_database=metadata_database,
    )
    land_result = run_alphaearth_land_model(
        countries="SE,DE,IE",
        output_dir=output_dir,
        eval_dir=tmp_path / "eval",
        metadata_database=metadata_database,
        earthengine_project=None,
    )

    result = run_feature_engineering(
        countries="SE,DE,IE",
        input_dir=output_dir,
        output_dir=output_dir,
        metadata_database=metadata_database,
    )

    payload = json.loads(result.output_path.read_text(encoding="utf-8"))
    land_payload = json.loads(land_result.output_path.read_text(encoding="utf-8"))
    land_by_cell = {
        record["cell_id"]: record
        for record in land_payload["records"]
    }
    assert result.record_count == _SUBSET_CELL_COUNT
    assert payload["normalization"]["method"] == "percentile_clipping"
    assert payload["congestion_blend_weights"] == {
        "ember_hub_country": 0.45,
        "opf_line_loading": 0.35,
        "opf_nodal_price_spread": 0.2,
    }

    required_fields = {
        "cell_id",
        "mean_price_eur_mwh",
        "price_volatility",
        "carbon_intensity_g_kwh",
        "congestion_index",
        "headroom_mw",
        "dist_hv_substation_km",
        "dist_fiber_km",
        "dist_ixp_km",
        "latency_proxy_ms",
        "solar_cf",
        "wind_cf",
        "water_dist_km",
        "cooling_degree_proxy",
        "lightgbm_score",
        "shap_values",
        "exclusion_flag",
        "missing_data_flags",
        "normalized_score_inputs",
        "map_overlay_values",
    }
    for record in payload["records"]:
        assert required_fields.issubset(record)
        assert record["carbon_method_visible"] == "ember_monthly_repeat"
        assert record["missing_data_flags"]["entsoe_hourly_generation_mix"] is True
        assert record["missing_data_flags"]["alphaearth_land"] is True
        assert record["missing_data_flags"]["siting_model"] is True
        assert record["source_methods"]["land"] == "fixture_land_proxy"
        assert record["source_methods"]["ml"] == "fixture_static_score"
        assert record["buildable_fraction"] == land_by_cell[record["cell_id"]]["buildable_fraction"]
        assert record["dc_similarity"] == land_by_cell[record["cell_id"]]["dc_similarity"]
        assert all(0 <= value <= 1 for value in record["normalized_score_inputs"].values())
        assert all(0 <= value <= 1 for value in record["map_overlay_values"].values())
        # Pipeline output must satisfy the SiteFeature API contract end-to-end:
        # the API repository validates each record through this same model,
        # so a schema drift here would silently bypass the trained values.
        SiteFeature.model_validate(record)

    with sqlite3.connect(metadata_database) as connection:
        row = connection.execute(
            """
            SELECT checksum_sha256, record_count
            FROM source_artifacts
            WHERE artifact_name = 'site_features_subset'
            AND country_scope = 'SE,DE,IE'
            """
        ).fetchone()

    assert row == (result.checksum_sha256, _SUBSET_CELL_COUNT)


def _write_ember_db_stub(path: Path) -> None:
    """Build a minimal ember_prices.db so the price overlay can run in tests."""

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
        # Real 2025 Ember values for SE/DE/IE (per ember/ember.md).
        connection.executemany(
            """
            INSERT INTO ember_price_profile
              (zone_id, iso3_code, sample_year, mean_price_eur_mwh,
               price_volatility, sample_hours)
              VALUES (?, ?, 2025, ?, ?, 8760)
            """,
            [
                ("SE", "SWE", 42.64, 38.24),
                ("DE", "DEU", 89.48, 50.81),
                ("IE", "IRL", 114.38, 54.34),
            ],
        )
        # 24-hour shape isn't asserted here (it's covered by test_hourly_price);
        # populate one row per hour so the price CLI's row-count check passes.
        for zone in ("SE", "DE", "IE"):
            connection.executemany(
                """
                INSERT INTO ember_price_hourly_shape
                  (zone_id, sample_year, hour, shape_multiplier, hour_mean_price_eur_mwh)
                  VALUES (?, 2025, ?, 1.0, 1.0)
                """,
                [(zone, hour) for hour in range(24)],
            )
        connection.commit()


def test_feature_engineering_overlays_ember_prices_when_artifact_present(
    tmp_path: Path,
) -> None:
    """When hourly_price_subset.json exists, per-cell prices match Ember.

    This is the integration seam between the new `ember/ingest.py` →
    `hourly_price` CLI → `feature_engineering` overlay. The end goal is that
    a SE/DE/IE cell in `site_features_subset.json` carries the Ember mean
    price (42.64 / 89.48 / 114.38 EUR/MWh), not the curated fixture value.
    """

    output_dir = tmp_path / "processed"
    metadata_database = tmp_path / "source_artifacts.db"
    ember_db = tmp_path / "ember" / "ember_prices.db"
    _write_ember_db_stub(ember_db)

    run_subset_ingestion(
        countries="SE,DE,IE",
        output_dir=output_dir,
        metadata_database=metadata_database,
    )
    run_hourly_carbon_ingestion(
        countries="SE,DE,IE",
        output_dir=output_dir,
        metadata_database=metadata_database,
    )
    run_alphaearth_land_model(
        countries="SE,DE,IE",
        output_dir=output_dir,
        eval_dir=tmp_path / "eval",
        metadata_database=metadata_database,
        earthengine_project=None,
    )
    run_hourly_price_ingestion(
        countries="SE,DE,IE",
        output_dir=output_dir,
        metadata_database=metadata_database,
        ember_db_path=ember_db,
    )

    result = run_feature_engineering(
        countries="SE,DE,IE",
        input_dir=output_dir,
        output_dir=output_dir,
        metadata_database=metadata_database,
    )

    payload = json.loads(result.output_path.read_text(encoding="utf-8"))
    expected_by_country = {"SE": 42.64, "DE": 89.48, "IE": 114.38}
    for record in payload["records"]:
        country = record["country_code"]
        # Every SE/DE/IE cell must now carry the Ember mean price, regardless
        # of what the curated fixture said.
        assert record["mean_price_eur_mwh"] == expected_by_country[country]
        # Fallback flag must reflect that Ember IS present.
        assert record["missing_data_flags"]["ember_hourly_price"] is False
        # source_methods must surface the active Ember method.
        assert record["source_methods"]["price"] == "ember_csv_local_db"


def test_feature_engineering_keeps_fixture_prices_without_ember_overlay(
    tmp_path: Path,
) -> None:
    """No hourly_price_subset.json ⇒ per-cell prices match the curated fixture.

    Pinning the inverse path — when the new artifact is absent, the blender
    must NOT silently zero out or rewrite the price; the fixture value
    survives untouched.
    """

    output_dir = tmp_path / "processed"
    metadata_database = tmp_path / "source_artifacts.db"

    run_subset_ingestion(
        countries="SE,DE,IE",
        output_dir=output_dir,
        metadata_database=metadata_database,
    )
    run_hourly_carbon_ingestion(
        countries="SE,DE,IE",
        output_dir=output_dir,
        metadata_database=metadata_database,
    )
    run_alphaearth_land_model(
        countries="SE,DE,IE",
        output_dir=output_dir,
        eval_dir=tmp_path / "eval",
        metadata_database=metadata_database,
        earthengine_project=None,
    )
    # NOTE: hourly_price_subset.json is intentionally NOT written here.

    result = run_feature_engineering(
        countries="SE,DE,IE",
        input_dir=output_dir,
        output_dir=output_dir,
        metadata_database=metadata_database,
    )

    payload = json.loads(result.output_path.read_text(encoding="utf-8"))
    fixture_by_cell = {site.cell_id: site for site in FEATURE_COLLECTION}
    for record in payload["records"]:
        fixture = fixture_by_cell[record["cell_id"]]
        assert record["mean_price_eur_mwh"] == fixture.mean_price_eur_mwh
        assert record["missing_data_flags"]["ember_hourly_price"] is True
        assert record["source_methods"]["price"] == "fixture_static_price"
