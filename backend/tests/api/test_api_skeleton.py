from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


def test_health_reports_fixture_mode() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data_mode"] == "fixture"
    assert payload["cache_key"].startswith("health:")


def test_assumptions_returns_typed_contract_with_cache_key() -> None:
    response = client.get("/assumptions")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data_mode"] == "fixture"
    assert payload["cache_key"].startswith("assumptions:")
    assert "optimizer" in payload["assumptions"]


def test_search_uses_real_site_feature_shape_and_filters_by_headroom() -> None:
    response = client.post(
        "/sites/search",
        json={"power_mw": 280, "workload_type": "training", "top_k": 5},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["requested_power_mw"] == 280
    assert payload["cache_key"].startswith("sites.search:")
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


def test_openapi_exposes_core_endpoint_contracts() -> None:
    schema = app.openapi()

    for path, method in {
        "/health": "get",
        "/layers/{layer_name}": "get",
        "/sites/search": "post",
        "/sites/{cell_id}": "get",
        "/sites/compare": "post",
        "/optimize/supply-mix": "post",
        "/assumptions": "get",
    }.items():
        assert path in schema["paths"]
        assert method in schema["paths"][path]

    components = schema["components"]["schemas"]
    assert "HealthResponse" in components
    assert "AssumptionsResponse" in components
    assert "ApiErrorResponse" in components
    for response_schema in (
        "LayerResponse",
        "SearchResponse",
        "SiteDetailResponse",
        "CompareResponse",
        "SupplyMixResponse",
    ):
        assert "cache_key" in components[response_schema]["properties"]


def test_detail_and_optimizer_complete_demo_contract() -> None:
    search_payload = client.post("/sites/search", json={"power_mw": 280, "top_k": 1}).json()
    cell_id = search_payload["results"][0]["site"]["cell_id"]

    detail = client.get(f"/sites/{cell_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["site"]["cell_id"] == cell_id
    assert detail_payload["cache_key"].startswith("sites.detail:")

    optimize = client.post(
        "/optimize/supply-mix",
        json={"cell_id": cell_id, "load_mw": 280, "load_profile": "flat_24_7"},
    )
    assert optimize.status_code == 200
    payload = optimize.json()
    assert payload["cell_id"] == cell_id
    assert payload["cache_key"].startswith("optimize.supply_mix:")
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
    assert payload["cache_key"].startswith("sites.compare:")
    assert [site["region_name"] for site in payload["sites"]] == ["Lulea / Boden", "Frankfurt West"]


def test_layer_composite_score_returns_geojson_with_computed_value() -> None:
    """Regression: `composite_score` is computed (not a SiteFeature column)."""
    response = client.get("/layers/composite_score")
    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    assert payload["cache_key"].startswith("layers:")
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
    assert payload["cache_key"].startswith("layers:")
    assert payload["features"][0]["properties"]["layer_name"] == "mean_price_eur_mwh"


def test_layer_unknown_name_404s() -> None:
    response = client.get("/layers/not_a_layer")
    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "layer_not_found",
            "message": "Unknown layer: not_a_layer",
        }
    }


def test_unknown_site_errors_are_clear_and_structured() -> None:
    detail = client.get("/sites/not-a-cell")
    compare = client.post(
        "/sites/compare",
        json={"cell_ids": ["851f25d7fffffff", "not-a-cell"]},
    )
    optimize = client.post(
        "/optimize/supply-mix",
        json={"cell_id": "not-a-cell", "load_mw": 280, "load_profile": "flat_24_7"},
    )

    for response in (detail, compare, optimize):
        assert response.status_code == 404
        payload = response.json()
        assert payload["detail"]["code"] == "site_not_found"
        assert payload["detail"]["message"] == "Unknown site cell: not-a-cell"


def test_cache_keys_are_stable_for_deterministic_requests() -> None:
    payload = {"power_mw": 280, "workload_type": "training", "top_k": 5}

    first = client.post("/sites/search", json=payload).json()["cache_key"]
    second = client.post("/sites/search", json=payload).json()["cache_key"]
    changed = client.post("/sites/search", json={**payload, "top_k": 4}).json()["cache_key"]

    assert first == second
    assert first != changed
