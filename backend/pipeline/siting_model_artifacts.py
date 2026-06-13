"""Artifact and metadata writes for the siting propensity model."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from backend.pipeline.artifacts import (
    ArtifactSummary,
    display_path,
    upsert_source_artifacts,
    write_json_artifact,
)
from backend.pipeline.siting_model_trainer import SitingModelFit
from backend.pipeline.siting_model_types import (
    ARTIFACT_VERSION,
    DETERMINISTIC_SEED,
    FEATURE_COLUMNS,
    METRICS_VERSION,
    SCHEMA_VERSION,
    SitingPrediction,
)

ROOT_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class SitingArtifactWrite:
    output_path: Path
    metrics_path: Path
    checksum_sha256: str
    metrics_checksum_sha256: str


def write_siting_model_artifacts(
    *,
    countries: Sequence[str],
    generated_at: str,
    output_dir: Path,
    eval_dir: Path,
    metadata_database: Path,
    fit: SitingModelFit,
) -> SitingArtifactWrite:
    output_path = output_dir / "siting_model_subset.json"
    checksum = write_json_artifact(
        output_path,
        _artifact_payload(
            countries=countries,
            generated_at=generated_at,
            fit=fit,
        ),
    )

    metrics_path = eval_dir / "siting_model_metrics.json"
    metrics_checksum = write_json_artifact(
        metrics_path,
        _metrics_payload(
            countries=countries,
            generated_at=generated_at,
            fit=fit,
            output_checksum=checksum,
        ),
    )
    _upsert_metadata(
        countries=countries,
        generated_at=generated_at,
        output_path=output_path,
        metrics_path=metrics_path,
        metadata_database=metadata_database,
        record_count=len(fit.predictions),
        checksum=checksum,
        metrics_checksum=metrics_checksum,
        source_status=fit.source_status,
        fallback=fit.fallback,
    )
    return SitingArtifactWrite(
        output_path=output_path,
        metrics_path=metrics_path,
        checksum_sha256=checksum,
        metrics_checksum_sha256=metrics_checksum,
    )


def _artifact_payload(
    *,
    countries: Sequence[str],
    generated_at: str,
    fit: SitingModelFit,
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_version": ARTIFACT_VERSION,
        "deterministic_seed": DETERMINISTIC_SEED,
        "generated_at": generated_at,
        "countries": list(countries),
        "source": "Loadstar siting propensity model",
        "source_status": fit.source_status,
        "active_method": fit.active_method,
        "feature_columns": list(FEATURE_COLUMNS),
        "label_summary": fit.metrics["label_summary"],
        "split_strategy": fit.metrics["split_strategy"],
        "feature_importance": fit.feature_importance,
        "fallback": fit.fallback,
        "model": fit.model_payload,
        "records": [_prediction_record(prediction) for prediction in fit.predictions],
    }


def _metrics_payload(
    *,
    countries: Sequence[str],
    generated_at: str,
    fit: SitingModelFit,
    output_checksum: str,
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_version": METRICS_VERSION,
        "deterministic_seed": DETERMINISTIC_SEED,
        "generated_at": generated_at,
        "countries": list(countries),
        "source_status": fit.source_status,
        "active_method": fit.active_method,
        "fallback": fit.fallback,
        "model_artifact_checksum_sha256": output_checksum,
        **fit.metrics,
    }


def _prediction_record(prediction: SitingPrediction) -> dict[str, object]:
    return {
        "cell_id": prediction.cell_id,
        "country_code": prediction.country_code,
        "region_name": prediction.region_name,
        "viability_score": prediction.viability_score,
        "shap_values": prediction.shap_values,
        "split": prediction.split,
        "label": prediction.label,
        "source_method": prediction.source_method,
    }


def _upsert_metadata(
    *,
    countries: Sequence[str],
    generated_at: str,
    output_path: Path,
    metrics_path: Path,
    metadata_database: Path,
    record_count: int,
    checksum: str,
    metrics_checksum: str,
    source_status: str,
    fallback: str | None,
) -> None:
    status = "processed" if source_status == "trained" else "fallback_processed"
    upsert_source_artifacts(
        metadata_database=metadata_database,
        countries=countries,
        generated_at=generated_at,
        artifacts=[
            ArtifactSummary(
                name="siting_model_subset",
                source="Loadstar siting propensity model",
                status=status,
                source_status=source_status,
                path=display_path(output_path, ROOT_DIR),
                checksum_sha256=checksum,
                artifact_version=ARTIFACT_VERSION,
                record_count=record_count,
                fallback=fallback,
                notes="Per-cell viability scores and SHAP-style feature contributions.",
            ),
            ArtifactSummary(
                name="siting_model_metrics",
                source="Loadstar siting propensity evaluation",
                status="processed",
                source_status=source_status,
                path=display_path(metrics_path, ROOT_DIR),
                checksum_sha256=metrics_checksum,
                artifact_version=METRICS_VERSION,
                record_count=record_count,
                fallback=fallback,
                notes="AUC, precision@k, feature importance, labels, and geography split details.",
            ),
        ],
    )
