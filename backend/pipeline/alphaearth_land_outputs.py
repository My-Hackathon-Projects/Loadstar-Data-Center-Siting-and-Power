"""Fallback records and evaluation payloads for AlphaEarth land modeling."""

from __future__ import annotations

from collections.abc import Sequence

from backend.engine.contracts import SiteFeature
from backend.pipeline.alphaearth_land_types import (
    ALPHAEARTH_COLLECTION_ID,
    ALPHAEARTH_YEAR,
    DETERMINISTIC_SEED,
    EMBEDDING_BANDS,
    METRICS_VERSION,
    RANDOM_FOREST_TREES,
    SCHEMA_VERSION,
    TRAIN_FRACTION,
    LandLabelPoint,
)
from backend.pipeline.alphaearth_land_utils import optional_float, optional_int


def fallback_records(sites: Sequence[SiteFeature]) -> list[dict[str, object]]:
    return [
        {
            "cell_id": site.cell_id,
            "country_code": site.country_code,
            "region_name": site.region_name,
            "latitude": site.latitude,
            "longitude": site.longitude,
            "resolution": site.resolution,
            "buildable_fraction": round(site.buildable_fraction, 4),
            "dc_similarity": round(site.dc_similarity, 4),
            "source_method": "fixture_land_proxy",
            "model_output_status": "fallback",
        }
        for site in sites
    ]


def fallback_label_predictions(
    labels: Sequence[LandLabelPoint],
    sites: Sequence[SiteFeature],
) -> list[dict[str, object]]:
    site_by_cell = {site.cell_id: site for site in sites}
    predictions: list[dict[str, object]] = []
    for label in labels:
        if label.split != "heldout":
            continue
        site = site_by_cell[label.cell_id]
        predictions.append(
            {
                "label_id": label.label_id,
                "cell_id": label.cell_id,
                "buildable_label": label.buildable_label,
                "dc_label": label.dc_label,
                "buildable_prediction": round(site.buildable_fraction, 4),
                "dc_prediction": round(site.dc_similarity, 4),
                "source_method": "fixture_land_proxy",
            }
        )
    return predictions


def metrics_payload(
    *,
    countries: Sequence[str],
    generated_at: str,
    source_status: str,
    active_method: str,
    labels: Sequence[LandLabelPoint],
    heldout_predictions: Sequence[dict[str, object]],
    sites: Sequence[SiteFeature],
    fallback: str | None,
    earthengine_error: str | None,
    output_checksum: str,
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_version": METRICS_VERSION,
        "deterministic_seed": DETERMINISTIC_SEED,
        "generated_at": generated_at,
        "countries": list(countries),
        "source_status": source_status,
        "active_method": active_method,
        "alphaearth_collection": ALPHAEARTH_COLLECTION_ID,
        "alphaearth_year": ALPHAEARTH_YEAR,
        "random_forest": {
            "trees": RANDOM_FOREST_TREES,
            "seed": DETERMINISTIC_SEED,
            "train_fraction": TRAIN_FRACTION,
            "embedding_band_count": len(EMBEDDING_BANDS),
        },
        "label_summary": _label_summary(labels),
        "heldout_metrics": _heldout_metrics(heldout_predictions),
        "heldout_labels": list(heldout_predictions),
        "manual_map_checks": _manual_map_checks(sites, source_status),
        "fallback": fallback,
        "earthengine_error": earthengine_error,
        "output_checksum_sha256": output_checksum,
    }


def _label_summary(labels: Sequence[LandLabelPoint]) -> dict[str, object]:
    return {
        "total_count": len(labels),
        "train_count": sum(1 for label in labels if label.split == "train"),
        "heldout_count": sum(1 for label in labels if label.split == "heldout"),
        "buildable_positive_count": sum(1 for label in labels if label.buildable_label == 1),
        "buildable_negative_count": sum(1 for label in labels if label.buildable_label == 0),
        "dc_positive_count": sum(1 for label in labels if label.dc_label == 1),
        "dc_negative_count": sum(1 for label in labels if label.dc_label == 0),
        "label_sources": sorted({label.label_source for label in labels}),
    }


def _heldout_metrics(predictions: Sequence[dict[str, object]]) -> dict[str, object]:
    if not predictions:
        return {
            "buildable_accuracy": None,
            "dc_accuracy": None,
            "heldout_count": 0,
        }
    buildable_correct = 0
    dc_correct = 0
    usable_buildable = 0
    usable_dc = 0
    for prediction in predictions:
        buildable_label = optional_int(prediction.get("buildable_label"))
        buildable_score = optional_float(prediction.get("buildable_prediction"))
        if buildable_label is not None and buildable_score is not None:
            usable_buildable += 1
            buildable_correct += int((1 if buildable_score >= 0.5 else 0) == buildable_label)
        dc_label = optional_int(prediction.get("dc_label"))
        dc_score = optional_float(prediction.get("dc_prediction"))
        if dc_label is not None and dc_score is not None:
            usable_dc += 1
            dc_correct += int((1 if dc_score >= 0.5 else 0) == dc_label)
    return {
        "buildable_accuracy": _accuracy(buildable_correct, usable_buildable),
        "dc_accuracy": _accuracy(dc_correct, usable_dc),
        "heldout_count": len(predictions),
    }


def _manual_map_checks(sites: Sequence[SiteFeature], source_status: str) -> list[dict[str, object]]:
    status = "sample_required" if source_status == "earth_engine" else "not_performed"
    note = (
        "Review AlphaEarth output against current satellite basemap before expanding."
        if source_status == "earth_engine"
        else "Fallback fixture proxy; manual basemap review still required."
    )
    return [
        {
            "cell_id": site.cell_id,
            "country_code": site.country_code,
            "region_name": site.region_name,
            "status": status,
            "notes": note,
        }
        for site in sites
    ]


def _accuracy(correct: int, total: int) -> float | None:
    if total == 0:
        return None
    return round(correct / total, 4)
