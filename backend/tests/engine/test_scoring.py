from backend.engine.assumptions import DEFAULT_WEIGHTS
from backend.engine.contracts import SearchRequest
from backend.engine.fixtures import FEATURE_COLLECTION
from backend.engine.scoring import search_sites

EXPECTED_FACTORS = (
    "price",
    "carbon",
    "congestion",
    "grid",
    "connectivity",
    "land",
    "ml",
)


def test_search_filters_exclusions_and_insufficient_headroom(monkeypatch) -> None:
    eligible = FEATURE_COLLECTION[0].model_copy(
        update={"cell_id": "eligible", "headroom_mw": 300, "exclusion_flag": False}
    )
    excluded = FEATURE_COLLECTION[1].model_copy(
        update={"cell_id": "excluded", "headroom_mw": 300, "exclusion_flag": True}
    )
    low_headroom = FEATURE_COLLECTION[2].model_copy(
        update={"cell_id": "low-headroom", "headroom_mw": 100, "exclusion_flag": False}
    )
    monkeypatch.setattr(
        "backend.engine.scoring.FEATURE_COLLECTION",
        [eligible, excluded, low_headroom],
    )

    response = search_sites(SearchRequest(power_mw=280, top_k=20))

    assert [result.site.cell_id for result in response.results] == ["eligible"]


def test_search_returns_deterministic_additive_score_breakdown() -> None:
    response = search_sites(SearchRequest(power_mw=280, top_k=8))

    assert [result.site.region_name for result in response.results] == [
        "Lulea / Boden",
        "Sundsvall",
        "Umea",
        "Frankfurt West",
    ]
    for result in response.results:
        assert set(result.score_breakdown) == set(EXPECTED_FACTORS)
        assert set(result.score_contributions) == set(EXPECTED_FACTORS)
        assert [item.factor for item in result.score_explanations] == list(EXPECTED_FACTORS)
        assert all(0.0 <= score <= 1.0 for score in result.score_breakdown.values())
        expected_score = round(sum(result.score_contributions.values()), 4)
        assert result.composite_score == expected_score


def test_score_contributions_use_request_weights() -> None:
    response = search_sites(
        SearchRequest(
            power_mw=280,
            top_k=1,
            weights={
                **DEFAULT_WEIGHTS,
                "price": 0.5,
                "carbon": 0.1,
            },
        )
    )
    result = response.results[0]

    assert result.score_contributions["price"] == round(result.score_breakdown["price"] * 0.5, 4)
    assert result.score_contributions["carbon"] == round(
        result.score_breakdown["carbon"] * 0.1,
        4,
    )
    assert result.score_explanations[0].raw_value
    assert result.score_explanations[0].direction in {
        "lower_is_better",
        "higher_is_better",
        "composite",
    }


def test_scale_band_warnings_are_thresholded() -> None:
    assert [warning.code for warning in search_sites(SearchRequest(power_mw=10)).warnings] == [
        "small_load"
    ]
    assert [warning.code for warning in search_sites(SearchRequest(power_mw=20)).warnings] == []
    assert [warning.code for warning in search_sites(SearchRequest(power_mw=700)).warnings] == []
    assert [warning.code for warning in search_sites(SearchRequest(power_mw=701)).warnings] == [
        "large_load"
    ]


# --- Trained-model wiring: ml + land factors ----------------------------------
#
# The `ml` factor must consume `lightgbm_score` (the LightGBM siting model
# output, weight 0.08 per scoring_engine.md), and the `land` factor must blend
# `buildable_fraction` and `dc_similarity` from AlphaEarth (also weight 0.08).
# These tests pin that wiring so a refactor cannot silently swap the field
# names without a CI signal.


def _two_site_fixture(*, lgbm_a: float, lgbm_b: float):
    """Two cells identical except for `lightgbm_score`. Used to isolate one factor."""

    site_a = FEATURE_COLLECTION[0].model_copy(
        update={"cell_id": "site-a", "lightgbm_score": lgbm_a}
    )
    site_b = FEATURE_COLLECTION[0].model_copy(
        update={"cell_id": "site-b", "lightgbm_score": lgbm_b}
    )
    return [site_a, site_b]


def test_ml_factor_consumes_lightgbm_score() -> None:
    """Higher lightgbm_score → higher ml breakdown score, all else equal."""

    sites = _two_site_fixture(lgbm_a=0.20, lgbm_b=0.95)
    response = search_sites(SearchRequest(power_mw=1.0, top_k=2), sites)

    by_cell = {r.site.cell_id: r for r in response.results}
    assert by_cell["site-b"].score_breakdown["ml"] > by_cell["site-a"].score_breakdown["ml"]
    # The ml raw_value must surface the lightgbm_score; protects against a
    # future swap to a different field name.
    ml_explanation = next(
        e for e in by_cell["site-b"].score_explanations if e.factor == "ml"
    )
    assert "ML viability" in ml_explanation.raw_value


def test_land_factor_blends_buildable_and_dc_similarity() -> None:
    """`land` averages buildable_fraction and dc_similarity, both higher-is-better."""

    site_low = FEATURE_COLLECTION[0].model_copy(
        update={"cell_id": "low-land", "buildable_fraction": 0.10, "dc_similarity": 0.10}
    )
    site_high = FEATURE_COLLECTION[0].model_copy(
        update={"cell_id": "high-land", "buildable_fraction": 0.90, "dc_similarity": 0.90}
    )
    response = search_sites(SearchRequest(power_mw=1.0, top_k=2), [site_low, site_high])

    by_cell = {r.site.cell_id: r for r in response.results}
    high_land = by_cell["high-land"].score_breakdown["land"]
    low_land = by_cell["low-land"].score_breakdown["land"]
    assert high_land > low_land
    land_explanation = next(
        e for e in by_cell["high-land"].score_explanations if e.factor == "land"
    )
    # The composite raw_value must mention both inputs so users can read the
    # source of the score in the explain panel.
    assert "buildable" in land_explanation.raw_value
    assert "data-center similarity" in land_explanation.raw_value


def test_default_weights_for_ml_and_land_match_scoring_engine_md() -> None:
    """scoring_engine.md fixes ml and land weights at 0.08 each. Pin it."""

    assert DEFAULT_WEIGHTS["ml"] == 0.08
    assert DEFAULT_WEIGHTS["land"] == 0.08


def test_ml_weight_propagates_to_contribution() -> None:
    """Doubling the ml weight doubles the ml contribution."""

    custom_weights = {**DEFAULT_WEIGHTS, "ml": 0.16}
    response = search_sites(
        SearchRequest(power_mw=280, top_k=1, weights=custom_weights)
    )
    result = response.results[0]
    assert result.score_contributions["ml"] == round(result.score_breakdown["ml"] * 0.16, 4)


def test_land_weight_propagates_to_contribution() -> None:
    """Doubling the land weight doubles the land contribution."""

    custom_weights = {**DEFAULT_WEIGHTS, "land": 0.16}
    response = search_sites(
        SearchRequest(power_mw=280, top_k=1, weights=custom_weights)
    )
    result = response.results[0]
    assert result.score_contributions["land"] == round(
        result.score_breakdown["land"] * 0.16, 4
    )
