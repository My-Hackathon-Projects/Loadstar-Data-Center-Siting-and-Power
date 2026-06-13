import json
import sqlite3
from pathlib import Path

from backend.engine.contracts import SiteFeature
from backend.pipeline.alphaearth_land import run_alphaearth_land_model
from backend.pipeline.feature_engineering import run_feature_engineering
from backend.pipeline.hourly_carbon import run_hourly_carbon_ingestion
from backend.pipeline.subset_ingestion import run_subset_ingestion


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
    # FEATURE_COLLECTION holds 10 fixture sites across SE, DE, IE (4+3+3).
    assert result.record_count == 10
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

    assert row == (result.checksum_sha256, 10)
