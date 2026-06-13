"""Deterministic representative-day profiles for the supply optimizer."""

import math

from backend.engine.contracts import SiteFeature
from backend.engine.optimizer_constants import HOURS_PER_DAY


def build_load_profile(load_mw: float, load_profile: str) -> list[float]:
    """Return a deterministic 24-hour load profile with the requested average MW."""

    if load_profile == "spiky_training":
        shape = [
            0.72,
            0.70,
            0.69,
            0.70,
            0.74,
            0.84,
            0.96,
            1.06,
            1.16,
            1.28,
            1.34,
            1.22,
            1.10,
            1.04,
            0.98,
            1.02,
            1.12,
            1.24,
            1.38,
            1.42,
            1.30,
            1.12,
            0.92,
            0.80,
        ]
        mean_shape = sum(shape) / len(shape)
        return [load_mw * factor / mean_shape for factor in shape]
    return [load_mw for _ in range(HOURS_PER_DAY)]


def build_wind_profile(mean_cf: float) -> list[float]:
    """Return an hourly wind capacity-factor profile with the requested mean."""

    raw = [
        1.04
        + 0.20 * math.sin((hour + 2) * math.pi / 12)
        + 0.08 * math.sin((hour + 5) * math.pi / 6)
        for hour in range(HOURS_PER_DAY)
    ]
    return _normalized_capacity_profile(mean_cf, raw, minimum=0.08, maximum=0.72)


def build_solar_profile(mean_cf: float) -> list[float]:
    """Return an hourly solar capacity-factor profile with the requested mean."""

    daylight = [max(0.0, math.sin((hour - 6) * math.pi / 13)) for hour in range(HOURS_PER_DAY)]
    return _normalized_capacity_profile(mean_cf, daylight, minimum=0.0, maximum=0.88)


def build_grid_price_profile(site: SiteFeature) -> list[float]:
    """Return deterministic hourly grid prices from mean price and volatility."""

    volatility = min(site.price_volatility, site.mean_price_eur_mwh * 0.35)
    return [
        max(
            1.0,
            site.mean_price_eur_mwh
            + 0.35 * volatility * math.sin((hour - 7) * math.pi / 12)
            + 0.15 * volatility * math.sin(hour * math.pi / 6),
        )
        for hour in range(HOURS_PER_DAY)
    ]


def _normalized_capacity_profile(
    mean_cf: float,
    raw: list[float],
    *,
    minimum: float,
    maximum: float,
) -> list[float]:
    if not raw:
        return []
    raw_mean = sum(raw) / len(raw)
    if raw_mean <= 0:
        return [0.0 for _ in raw]
    scaled = [value * mean_cf / raw_mean for value in raw]
    clipped = [min(maximum, max(minimum, value)) for value in scaled]
    clipped_mean = sum(clipped) / len(clipped)
    if clipped_mean <= 0:
        return clipped
    return [min(maximum, max(minimum, value * mean_cf / clipped_mean)) for value in clipped]
