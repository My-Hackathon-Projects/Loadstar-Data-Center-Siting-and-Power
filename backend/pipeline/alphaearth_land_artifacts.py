"""Artifact and metadata writes for the AlphaEarth land pipeline."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from backend.engine.contracts import SiteFeature
from backend.pipeline.alphaearth_land_outputs import metrics_payload
from backend.pipeline.alphaearth_land_types import (
    ALPHAEARTH_COLLECTION_ID,
    ALPHAEARTH_YEAR,
    ARTIFACT_VERSION,
    DETERMINISTIC_SEED,
    EMBEDDING_BANDS,
    METRICS_VERSION,
    RANDOM_FOREST_TREES,
    SCHEMA_VERSION,
    TRAIN_FRACTION,
    LandLabelPoint,
)
from backend.pipeline.artifacts import (
    ArtifactSummary,
    display_path,
    upsert_source_artifacts,
    write_json_artifact,
)

ROOT_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class LandArtifactWrite:
    output_path: Path
    metrics_path: Path
    checksum_sha256: str
    metrics_checksum_sha256: str


def write_land_artifacts(
    *,
    countries: Sequence[str],
    generated_at: str,
    output_dir: Path,
    eval_dir: Path,
    metadata_database: Path,
    source_status: str,
    active_method: str,
    fallback: str | None,
    earthengine_error: str | None,
    records: Sequence[dict[str, object]],
    heldout_predictions: Sequence[dict[str, object]],
    labels: Sequence[LandLabelPoint],
    sites: Sequence[SiteFeature],
) -> LandArtifactWrite:
    output_path = output_dir / "alphaearth_land_subset.json"
    checksum = write_json_artifact(
        output_path,
        _artifact_payload(
            countries=countries,
            generated_at=generated_at,
            source_status=source_status,
            active_method=active_method,
            fallback=fallback,
            earthengine_error=earthengine_error,
            records=records,
        ),
    )

    metrics_path = eval_dir / "alphaearth_land_metrics.json"
    metrics_checksum = write_json_artifact(
        metrics_path,
        metrics_payload(
            countries=countries,
            generated_at=generated_at,
            source_status=source_status,
            active_method=active_method,
            labels=labels,
            heldout_predictions=heldout_predictions,
            sites=sites,
            fallback=fallback,
            earthengine_error=earthengine_error,
            output_checksum=checksum,
        ),
    )
    _upsert_metadata(
        countries=countries,
        generated_at=generated_at,
        output_path=output_path,
        metrics_path=metrics_path,
        metadata_database=metadata_database,
        record_count=len(records),
        label_count=len(labels),
        checksum=checksum,
        metrics_checksum=metrics_checksum,
        source_status=source_status,
        fallback=fallback,
    )
    return LandArtifactWrite(
        output_path=output_path,
        metrics_path=metrics_path,
        checksum_sha256=checksum,
        metrics_checksum_sha256=metrics_checksum,
    )


def _artifact_payload(
    *,
    countries: Sequence[str],
    generated_at: str,
    source_status: str,
    active_method: str,
    fallback: str | None,
    earthengine_error: str | None,
    records: Sequence[dict[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_version": ARTIFACT_VERSION,
        "deterministic_seed": DETERMINISTIC_SEED,
        "generated_at": generated_at,
        "countries": list(countries),
        "source": "Google Satellite Embedding / AlphaEarth Foundations",
        "source_status": source_status,
        "active_method": active_method,
        "alphaearth_collection": ALPHAEARTH_COLLECTION_ID,
        "alphaearth_year": ALPHAEARTH_YEAR,
        "embedding_bands": list(EMBEDDING_BANDS),
        "random_forest": {
            "trees": RANDOM_FOREST_TREES,
            "seed": DETERMINISTIC_SEED,
            "train_fraction": TRAIN_FRACTION,
        },
        "fallback": fallback,
        "earthengine_error": earthengine_error,
        "records": list(records),
    }


def _upsert_metadata(
    *,
    countries: Sequence[str],
    generated_at: str,
    output_path: Path,
    metrics_path: Path,
    metadata_database: Path,
    record_count: int,
    label_count: int,
    checksum: str,
    metrics_checksum: str,
    source_status: str,
    fallback: str | None,
) -> None:
    upsert_source_artifacts(
        metadata_database=metadata_database,
        countries=countries,
        generated_at=generated_at,
        artifacts=[
            ArtifactSummary(
                name="alphaearth_land_subset",
                source="Google Satellite Embedding / AlphaEarth Foundations",
                status="processed" if source_status == "earth_engine" else "fallback_processed",
                source_status=source_status,
                path=display_path(output_path, ROOT_DIR),
                checksum_sha256=checksum,
                artifact_version=ARTIFACT_VERSION,
                record_count=record_count,
                fallback=fallback,
                notes="Per-cell buildable_fraction and dc_similarity land features.",
            ),
            ArtifactSummary(
                name="alphaearth_land_metrics",
                source="Loadstar AlphaEarth land evaluation",
                status="processed",
                source_status=source_status,
                path=display_path(metrics_path, ROOT_DIR),
                checksum_sha256=metrics_checksum,
                artifact_version=METRICS_VERSION,
                record_count=label_count,
                fallback=fallback,
                notes="Held-out labels, deterministic metrics, and manual map-check records.",
            ),
        ],
    )
