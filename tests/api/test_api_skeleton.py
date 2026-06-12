from fastapi.testclient import TestClient

from api.app.main import app

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


def test_search_scale_band_warnings() -> None:
    small = client.post("/sites/search", json={"power_mw": 10}).json()
    large = client.post("/sites/search", json={"power_mw": 800}).json()
    assert small["warnings"][0]["code"] == "small_load"
    assert large["warnings"][0]["code"] == "large_load"


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
    assert payload["pareto_frontier"]
    assert payload["dispatch_preview"]
    assert "hourly_24_7_cfe_share" in payload


def test_compare_sites() -> None:
    response = client.post(
        "/sites/compare",
        json={"cell_ids": ["851f25d7fffffff", "851fa62bfffffff"]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert [site["region_name"] for site in payload["sites"]] == ["Lulea / Boden", "Frankfurt West"]
