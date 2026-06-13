"""Pipeline-internal shared dataclasses and helpers used by the subset
ingestion orchestrator and its extracted builders.

This module exists only to break the import cycle between
`subset_ingestion.py` (orchestrator) and the per-source builder modules
(`_network.py`, `_layers.py`). It is not part of the package's public surface;
callers outside `backend.pipeline` should not import from here.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt

from backend.engine.contracts import SiteFeature
from backend.pipeline.constants import DETERMINISTIC_SEED

# Schema/artifact version pins live with the helpers because `_base_payload`
# stamps them into every emitted artifact.
SCHEMA_VERSION = "loadstar.subset_ingestion.v1"
ARTIFACT_VERSION = "subset-fixture-proxy-v1"


@dataclass(frozen=True)
class SourceDecision:
    source: str
    status: str
    fallback: str | None


@dataclass(frozen=True)
class NetworkLine:
    line_id: str
    country_code: str
    from_cell_id: str
    to_cell_id: str
    length_km_proxy: float
    capacity_mw_proxy: float
    congestion_index_proxy: float


@dataclass(frozen=True)
class ArtifactBuild:
    name: str
    file_name: str
    source: str
    status: str
    source_status: str
    record_count: int
    fallback: str | None
    notes: str
    payload: dict[str, object]


def base_payload(
    *,
    source: str,
    countries: Sequence[str],
    generated_at: str,
    source_status: str,
    fallback: str | None,
    records: list[dict[str, object]],
) -> dict[str, object]:
    """Wrap per-source records in the canonical artifact envelope."""

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_version": ARTIFACT_VERSION,
        "deterministic_seed": DETERMINISTIC_SEED,
        "generated_at": generated_at,
        "source": source,
        "source_status": source_status,
        "countries": list(countries),
        "fallback": fallback,
        "records": records,
    }


def decision_for(decisions: Sequence[SourceDecision], source_prefix: str) -> SourceDecision:
    """Look up the SourceDecision whose `source` starts with the given prefix."""

    return next(decision for decision in decisions if decision.source.startswith(source_prefix))


def node_id(site: SiteFeature) -> str:
    """Stable PyPSA-style node id derived from country code + cell suffix."""

    return f"{site.country_code}-{site.cell_id[-6:]}"


def distance_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    """Great-circle distance in kilometres between two lat/lon pairs."""

    radius_km = 6371.0
    delta_lat = radians(lat_b - lat_a)
    delta_lon = radians(lon_b - lon_a)
    start_lat = radians(lat_a)
    end_lat = radians(lat_b)
    haversine = sin(delta_lat / 2) ** 2 + cos(start_lat) * cos(end_lat) * sin(delta_lon / 2) ** 2
    return 2 * radius_km * asin(sqrt(haversine))


def country_averages(sites: Sequence[SiteFeature]) -> dict[str, dict[str, float]]:
    """Per-country mean of price, carbon, capacity factors, and congestion."""

    averages: dict[str, dict[str, float]] = {}
    for country in sorted({site.country_code for site in sites}):
        country_sites = [site for site in sites if site.country_code == country]
        count = len(country_sites)
        averages[country] = {
            "price": sum(site.mean_price_eur_mwh for site in country_sites) / count,
            "carbon": sum(site.carbon_intensity_g_kwh for site in country_sites) / count,
            "solar_cf": sum(site.solar_cf for site in country_sites) / count,
            "wind_cf": sum(site.wind_cf for site in country_sites) / count,
            "congestion": sum(site.congestion_index for site in country_sites) / count,
        }
    return averages


def hourly_shape(hour: int) -> dict[str, float]:
    """Deterministic hour-of-day multipliers for price, carbon, solar, wind."""

    daytime = 8 <= hour <= 18
    evening_peak = 17 <= hour <= 21
    night = hour <= 5 or hour >= 23
    return {
        "price": 1.18 if evening_peak else 0.88 if night else 1.0,
        "carbon": 1.08 if evening_peak else 0.94 if night else 1.0,
        "solar": 1.0 if daytime else 0.0,
        "wind": 1.08 if night else 0.96 if daytime else 1.0,
    }


def osm_record(
    site: SiteFeature,
    asset_type: str,
    value_key: str,
    value: float | bool,
) -> dict[str, object]:
    """Single OSM-derived feature row keyed by site cell_id and asset type."""

    return {
        "asset_type": asset_type,
        "cell_id": site.cell_id,
        "country_code": site.country_code,
        value_key: value,
        "source_method": f"fixture_{asset_type}",
    }
