"""Shared types and constants for the siting propensity model."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = "loadstar.siting_model.v1"
ARTIFACT_VERSION = "siting-model-v1"
METRICS_VERSION = "siting-model-metrics-v1"
DETERMINISTIC_SEED = 20260612
NEGATIVES_PER_POSITIVE = 3
OSM_POSITIVE_SIMILARITY_THRESHOLD = 0.75

FEATURE_COLUMNS = (
    "mean_price_eur_mwh",
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
    "buildable_fraction",
    "dc_similarity",
)

CURATED_KNOWN_DC_CELLS = frozenset(
    {
        "851f25d7fffffff",  # Lulea / Boden
        "851f2a6bfffffff",  # Stockholm North
        "851fa62bfffffff",  # Frankfurt West
        "85195da7fffffff",  # Dublin West
    }
)


@dataclass(frozen=True)
class TrainingExample:
    example_id: str
    cell_id: str
    country_code: str
    label: int
    split: str
    feature_values: dict[str, float]
    label_source: str


@dataclass(frozen=True)
class CellFeatureVector:
    cell_id: str
    country_code: str
    region_name: str
    feature_values: dict[str, float]
    split: str
    label: int | None
    label_source: str | None
    excluded: bool


@dataclass(frozen=True)
class SitingPrediction:
    cell_id: str
    country_code: str
    region_name: str
    viability_score: float
    shap_values: dict[str, float]
    split: str
    label: int | None
    source_method: str


@dataclass(frozen=True)
class SitingModelResult:
    countries: tuple[str, ...]
    output_path: Path
    metrics_path: Path
    metadata_database: Path
    record_count: int
    checksum_sha256: str
    metrics_checksum_sha256: str
    source_status: str
