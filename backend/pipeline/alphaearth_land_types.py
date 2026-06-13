"""Shared types and constants for the AlphaEarth land pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from backend.pipeline.constants import DETERMINISTIC_SEED

SCHEMA_VERSION = "loadstar.alphaearth_land.v1"
ARTIFACT_VERSION = "alphaearth-land-v1"
METRICS_VERSION = "alphaearth-land-metrics-v1"
ALPHAEARTH_COLLECTION_ID = "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL"
ALPHAEARTH_YEAR = 2024
EMBEDDING_BANDS = tuple(f"A{index:02d}" for index in range(64))

# Re-export so downstream `from backend.pipeline.alphaearth_land_types import
# DETERMINISTIC_SEED` keeps working without churn.
__all__ = (
    "ALPHAEARTH_COLLECTION_ID",
    "ALPHAEARTH_YEAR",
    "ARTIFACT_VERSION",
    "DETERMINISTIC_SEED",
    "EMBEDDING_BANDS",
    "METRICS_VERSION",
    "SCHEMA_VERSION",
)
RANDOM_FOREST_TREES = 80
TRAIN_FRACTION = 0.8
H3_PROXY_BUFFER_METERS = 4500

Split = Literal["train", "heldout"]


@dataclass(frozen=True)
class LandLabelPoint:
    label_id: str
    cell_id: str
    country_code: str
    region_name: str
    latitude: float
    longitude: float
    buildable_label: int
    dc_label: int
    split: Split
    label_source: str


@dataclass(frozen=True)
class AlphaEarthLandResult:
    countries: tuple[str, ...]
    output_path: Path
    metrics_path: Path
    metadata_database: Path
    record_count: int
    checksum_sha256: str
    metrics_checksum_sha256: str
    source_status: str
