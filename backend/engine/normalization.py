"""Shared numeric normalization helpers for scoring and feature artifacts."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

DEFAULT_CLIP_LOWER_PERCENTILE = 5.0
DEFAULT_CLIP_UPPER_PERCENTILE = 95.0


@dataclass(frozen=True)
class ClippingBounds:
    """Inclusive low/high bounds used before linear normalization."""

    lower: float
    upper: float


def percentile(values: Sequence[float], percentile_value: float) -> float:
    """Return a linearly interpolated percentile over finite values."""

    if percentile_value < 0 or percentile_value > 100:
        raise ValueError("percentile_value must be between 0 and 100.")
    sorted_values = sorted(value for value in values if math.isfinite(value))
    if not sorted_values:
        raise ValueError("Cannot compute percentile of an empty finite sequence.")
    if len(sorted_values) == 1:
        return sorted_values[0]

    position = (len(sorted_values) - 1) * percentile_value / 100
    lower_index = math.floor(position)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    fraction = position - lower_index
    return sorted_values[lower_index] + (
        sorted_values[upper_index] - sorted_values[lower_index]
    ) * fraction


def percentile_bounds(
    values: Sequence[float],
    *,
    lower_percentile: float = DEFAULT_CLIP_LOWER_PERCENTILE,
    upper_percentile: float = DEFAULT_CLIP_UPPER_PERCENTILE,
) -> ClippingBounds:
    """Return clipping bounds for a feature distribution."""

    if lower_percentile > upper_percentile:
        raise ValueError("lower_percentile must be less than or equal to upper_percentile.")
    return ClippingBounds(
        lower=percentile(values, lower_percentile),
        upper=percentile(values, upper_percentile),
    )


def normalize_value(
    value: float,
    bounds: ClippingBounds,
    *,
    lower_is_better: bool,
    degenerate_score: float = 1.0,
    missing_score: float = 0.0,
) -> float:
    """Clip and normalize a raw value into a bounded 0..1 score."""

    if not math.isfinite(value):
        return _clamp01(missing_score)
    if bounds.upper == bounds.lower:
        return _clamp01(degenerate_score)

    clipped = min(max(value, bounds.lower), bounds.upper)
    normalized = (clipped - bounds.lower) / (bounds.upper - bounds.lower)
    if lower_is_better:
        normalized = 1 - normalized
    return _clamp01(normalized)


def _clamp01(value: float) -> float:
    return min(max(value, 0.0), 1.0)
