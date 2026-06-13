import pytest

from backend.engine.normalization import normalize_value, percentile, percentile_bounds


def test_percentile_uses_linear_interpolation() -> None:
    assert percentile([10.0, 20.0, 30.0], 50) == 20.0
    assert percentile([0.0, 100.0], 25) == 25.0


def test_percentile_bounds_reject_invalid_ranges() -> None:
    with pytest.raises(ValueError, match="lower_percentile"):
        percentile_bounds([1.0, 2.0], lower_percentile=95, upper_percentile=5)


def test_normalize_value_clips_and_honors_direction() -> None:
    bounds = percentile_bounds([0.0, 50.0, 100.0], lower_percentile=0, upper_percentile=100)

    assert normalize_value(-10.0, bounds, lower_is_better=False) == 0.0
    assert normalize_value(110.0, bounds, lower_is_better=False) == 1.0
    assert normalize_value(25.0, bounds, lower_is_better=False) == 0.25
    assert normalize_value(25.0, bounds, lower_is_better=True) == 0.75


def test_normalize_value_handles_degenerate_and_missing_values() -> None:
    bounds = percentile_bounds([42.0, 42.0])

    assert normalize_value(42.0, bounds, lower_is_better=False, degenerate_score=0.5) == 0.5
    assert normalize_value(float("nan"), bounds, lower_is_better=False, missing_score=0.25) == 0.25
