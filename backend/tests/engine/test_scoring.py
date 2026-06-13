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
