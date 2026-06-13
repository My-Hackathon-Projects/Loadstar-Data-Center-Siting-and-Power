from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


def test_health_reports_fixture_mode() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "data_mode": "fixture"}


def test_search_uses_real_site_feature_shape_and_filters_by_headroom() -> None:
    response = client.post(
        "/sites/search",
        json={"power_mw": 280, "workload_type": "training", "top_k": 5},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["requested_power_mw"] == 280
    assert payload["warnings"] == []
    assert payload["results"]

    first_site = payload["results"][0]["site"]
    expected_fields = {
        "cell_id",
        "country_code",
        "region_name",
        "mean_price_eur_mwh",
        "carbon_intensity_g_kwh",
        "congestion_index",
        "headroom_mw",
        "dist_hv_substation_km",
        "dist_fiber_km",
        "dist_ixp_km",
        "buildable_fraction",
        "dc_similarity",
        "lightgbm_score",
        "shap_values",
        "exclusion_flag",
    }
    assert expected_fields.issubset(first_site.keys())
    assert all(result["site"]["headroom_mw"] >= 280 for result in payload["results"])
    for result in payload["results"]:
        assert set(result["score_breakdown"]) == {
            "price",
            "carbon",
            "congestion",
            "grid",
            "connectivity",
            "land",
            "ml",
        }
        assert set(result["score_contributions"]) == set(result["score_breakdown"])
        assert result["score_explanations"]
        assert all(
            {"factor", "score", "weight", "contribution", "raw_value", "direction"}.issubset(
                explanation
            )
            for explanation in result["score_explanations"]
        )


def test_search_scale_band_warnings() -> None:
    small = client.post("/sites/search", json={"power_mw": 10}).json()
    large = client.post("/sites/search", json={"power_mw": 800}).json()
    assert small["warnings"][0]["code"] == "small_load"
    assert large["warnings"][0]["code"] == "large_load"


def test_openapi_exposes_score_explanation_contract() -> None:
    schema = app.openapi()

    ranked_site = schema["components"]["schemas"]["RankedSite"]["properties"]
    assert "score_breakdown" in ranked_site
    assert "score_contributions" in ranked_site
    assert "score_explanations" in ranked_site
    assert "ScoreExplanation" in schema["components"]["schemas"]


def test_detail_and_optimizer_complete_demo_contract() -> None:
    search_payload = client.post("/sites/search", json={"power_mw": 280, "top_k": 1}).json()
    cell_id = search_payload["results"][0]["site"]["cell_id"]

    detail = client.get(f"/sites/{cell_id}")
    assert detail.status_code == 200
    assert detail.json()["site"]["cell_id"] == cell_id

    optimize = client.post(
        "/optimize/supply-mix",
        json={"cell_id": cell_id, "load_mw": 280, "load_profile": "flat_24_7"},
    )
    assert optimize.status_code == 200
    payload = optimize.json()
    assert payload["cell_id"] == cell_id
    assert payload["solver_status"] == "optimal"
    assert 8 <= len(payload["pareto_frontier"]) <= 12
    assert payload["dispatch_summary"]["total_load_mwh"] > 0
    assert payload["dispatch_preview"]
    first_dispatch = payload["dispatch_preview"][0]
    assert {
        "hour",
        "load_mw",
        "grid_mw",
        "wind_ppa_mw",
        "solar_ppa_mw",
        "onsite_solar_mw",
        "battery_charge_mw",
        "battery_discharge_mw",
        "battery_soc_mwh",
        "backup_mw",
        "curtailment_mw",
    }.issubset(first_dispatch)
    first_point = payload["pareto_frontier"][0]
    assert {"backup_share", "curtailment_share"}.issubset(first_point)
    assert "hourly_24_7_cfe_share" in payload


def test_compare_sites() -> None:
    response = client.post(
        "/sites/compare",
        json={"cell_ids": ["851f25d7fffffff", "851fa62bfffffff"]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert [site["region_name"] for site in payload["sites"]] == ["Lulea / Boden", "Frankfurt West"]


def test_layer_composite_score_returns_geojson_with_computed_value() -> None:
    """Regression: `composite_score` is computed (not a SiteFeature column)."""
    response = client.get("/layers/composite_score")
    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    assert payload["features"]
    for feature in payload["features"]:
        assert feature["properties"]["layer_name"] == "composite_score"
        score = feature["properties"]["layer_value"]
        # Composite score is a weighted sum of normalized 0..1 inputs, so bounded.
        assert 0.0 <= score <= 1.0


def test_layer_raw_field_returns_geojson() -> None:
    response = client.get("/layers/mean_price_eur_mwh")
    assert response.status_code == 200
    payload = response.json()
    assert payload["features"]
    assert payload["features"][0]["properties"]["layer_name"] == "mean_price_eur_mwh"


def test_layer_unknown_name_404s() -> None:
    response = client.get("/layers/not_a_layer")
    assert response.status_code == 404
