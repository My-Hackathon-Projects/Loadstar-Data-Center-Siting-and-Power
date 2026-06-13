"""Artifact loading and parsing for feature engineering.

Reads `hourly_carbon_subset.json`, `pypsa_clustered_opf.json`,
`ember_grids_congestion_layers.json`, `alphaearth_land_subset.json`, and
`siting_model_subset.json`; returns a `FeatureContext` that the blender
consumes. The orchestrator (`feature_engineering.py`) stays free of payload
parsing detail.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from backend.pipeline._value_parsers import clamp01, optional_float, optional_string


@dataclass(frozen=True)
class SitingModelFeature:
    viability_score: float
    shap_values: dict[str, float]


@dataclass(frozen=True)
class FeatureContext:
    hourly_carbon_by_country: dict[str, float]
    hourly_carbon_method: str
    land_by_cell: dict[str, dict[str, float]]
    land_method: str
    land_source_status: str
    model_by_cell: dict[str, SitingModelFeature]
    model_method: str
    model_source_status: str
    ember_country_congestion: dict[str, float]
    ember_hub_congestion: dict[str, float]
    line_loading_by_cell: dict[str, float]
    nodal_price_spread_by_cell: dict[str, float]
    summary: dict[str, object]


def load_context(input_dir: Path) -> FeatureContext:
    """Read the five upstream artifacts and assemble the per-cell context."""

    hourly_payload = _load_payload(input_dir / "hourly_carbon_subset.json")
    land_payload = _load_payload(input_dir / "alphaearth_land_subset.json")
    model_payload = _load_payload(input_dir / "siting_model_subset.json")
    opf_payload = _load_payload(input_dir / "pypsa_clustered_opf.json")
    congestion_payload = _load_payload(input_dir / "ember_grids_congestion_layers.json")
    hourly_records = _records(hourly_payload)
    land_records = _records(land_payload)
    model_records = _records(model_payload)
    opf_records = _records(opf_payload)
    congestion_records = _records(congestion_payload)
    active_method = optional_string(hourly_payload.get("active_method"), "missing")
    land_method = optional_string(
        land_payload.get("active_method"),
        "fixture_schema_compatible_proxy",
    )
    land_status = optional_string(land_payload.get("source_status"), "missing")
    model_method = optional_string(model_payload.get("active_method"), "fixture_static_score")
    model_status = optional_string(model_payload.get("source_status"), "missing")

    line_loading_by_cell, nodal_price_spread_by_cell = _opf_components(opf_records)
    country_congestion, hub_congestion = _congestion_components(congestion_records)
    summary: dict[str, object] = {
        "hourly_carbon_artifact": _payload_status(hourly_payload),
        "alphaearth_land_artifact": _payload_status(land_payload),
        "siting_model_artifact": _payload_status(model_payload),
        "opf_artifact": _payload_status(opf_payload),
        "congestion_artifact": _payload_status(congestion_payload),
    }
    return FeatureContext(
        hourly_carbon_by_country=_average_hourly_carbon(hourly_records),
        hourly_carbon_method=active_method,
        land_by_cell=_land_features(land_records),
        land_method=land_method,
        land_source_status=land_status,
        model_by_cell=_siting_model_features(model_records),
        model_method=model_method,
        model_source_status=model_status,
        ember_country_congestion=country_congestion,
        ember_hub_congestion=hub_congestion,
        line_loading_by_cell=line_loading_by_cell,
        nodal_price_spread_by_cell=nodal_price_spread_by_cell,
        summary=summary,
    )


def _opf_components(
    opf_records: Sequence[dict[str, object]],
) -> tuple[dict[str, float], dict[str, float]]:
    """Extract per-cell line loadings and nodal price spread from the OPF artifact."""

    if not opf_records:
        return {}, {}
    first = opf_records[0]
    line_loadings_raw = first.get("line_loadings")
    nodal_prices_raw = first.get("nodal_prices")
    line_values: dict[str, list[float]] = {}
    if isinstance(line_loadings_raw, list):
        for item in cast(list[object], line_loadings_raw):
            if not isinstance(item, dict):
                continue
            item_dict = cast(dict[str, object], item)
            loading = optional_float(item_dict.get("loading_percent"))
            if loading is None:
                continue
            for key in ("from_cell_id", "to_cell_id"):
                cell_id = item_dict.get(key)
                if isinstance(cell_id, str):
                    line_values.setdefault(cell_id, []).append(clamp01(loading / 100))
    line_loading_by_cell = {
        cell_id: sum(values) / len(values) for cell_id, values in line_values.items()
    }

    nodal_prices: dict[str, float] = {}
    if isinstance(nodal_prices_raw, list):
        for item in cast(list[object], nodal_prices_raw):
            if not isinstance(item, dict):
                continue
            item_dict = cast(dict[str, object], item)
            cell_id = item_dict.get("cell_id")
            price = optional_float(item_dict.get("nodal_price_eur_mwh"))
            if isinstance(cell_id, str) and price is not None:
                nodal_prices[cell_id] = price
    nodal_spread = _minmax(nodal_prices)
    return line_loading_by_cell, nodal_spread


def _congestion_components(
    congestion_records: Sequence[dict[str, object]],
) -> tuple[dict[str, float], dict[str, float]]:
    """Split the Ember congestion layer into per-country and per-hub maps."""

    country: dict[str, float] = {}
    hub: dict[str, float] = {}
    for record in congestion_records:
        layer_type = record.get("layer_type")
        if layer_type == "country_summary":
            country_code = record.get("country_code")
            value = optional_float(record.get("mean_congestion_index"))
            if isinstance(country_code, str) and value is not None:
                country[country_code] = value
        elif layer_type == "hub_proxy":
            cell_id = record.get("cell_id")
            value = optional_float(record.get("congestion_index"))
            if isinstance(cell_id, str) and value is not None:
                hub[cell_id] = value
    return country, hub


def _land_features(land_records: Sequence[dict[str, object]]) -> dict[str, dict[str, float]]:
    """Per-cell buildable_fraction + dc_similarity from the AlphaEarth artifact."""

    values: dict[str, dict[str, float]] = {}
    for record in land_records:
        cell_id = record.get("cell_id")
        buildable = optional_float(record.get("buildable_fraction"))
        similarity = optional_float(record.get("dc_similarity"))
        if isinstance(cell_id, str) and buildable is not None and similarity is not None:
            values[cell_id] = {
                "buildable_fraction": clamp01(buildable),
                "dc_similarity": clamp01(similarity),
            }
    return values


def _siting_model_features(
    model_records: Sequence[dict[str, object]],
) -> dict[str, SitingModelFeature]:
    """Per-cell viability score + SHAP contributions from the LightGBM artifact."""

    values: dict[str, SitingModelFeature] = {}
    for record in model_records:
        cell_id = record.get("cell_id")
        score = optional_float(record.get("viability_score"))
        shap_values = _shap_values(record.get("shap_values"))
        if isinstance(cell_id, str) and score is not None and shap_values:
            values[cell_id] = SitingModelFeature(
                viability_score=round(clamp01(score), 4),
                shap_values=shap_values,
            )
    return values


def _shap_values(raw: object) -> dict[str, float]:
    """Coerce a SHAP-like dict to {feature: rounded_float}; reject non-numeric values."""

    if not isinstance(raw, dict):
        return {}
    values: dict[str, float] = {}
    for key, value in cast(dict[object, object], raw).items():
        parsed = optional_float(value)
        if isinstance(key, str) and parsed is not None:
            values[key] = round(parsed, 6)
    return values


def _average_hourly_carbon(records: Sequence[dict[str, object]]) -> dict[str, float]:
    """Mean carbon-intensity per zone from the hourly artifact."""

    values: dict[str, list[float]] = {}
    for record in records:
        zone_id = record.get("zone_id")
        carbon = optional_float(record.get("carbon_g_kwh"))
        if isinstance(zone_id, str) and carbon is not None:
            values.setdefault(zone_id, []).append(carbon)
    return {zone_id: sum(items) / len(items) for zone_id, items in values.items()}


def _load_payload(path: Path) -> dict[str, object]:
    """Read a JSON object from disk, returning a 'missing' stub if the file is absent."""

    if not path.exists():
        return {
            "source_status": "missing",
            "records": [],
            "path": str(path),
        }
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return cast(dict[str, object], raw)


def _records(payload: dict[str, object]) -> list[dict[str, object]]:
    """Defensively pull a list-of-dicts out of the artifact `records` field."""

    raw = payload.get("records")
    if not isinstance(raw, list):
        return []
    records: list[dict[str, object]] = []
    for item in cast(list[object], raw):
        if isinstance(item, dict):
            records.append(cast(dict[str, object], item))
    return records


def _payload_status(payload: dict[str, object]) -> dict[str, object]:
    """Compact status dict surfaced in the feature artifact's source_context."""

    return {
        "schema_version": optional_string(payload.get("schema_version"), "missing"),
        "artifact_version": optional_string(payload.get("artifact_version"), "missing"),
        "source_status": optional_string(payload.get("source_status"), "missing"),
        "active_method": optional_string(payload.get("active_method"), "not_applicable"),
    }


def _minmax(values: dict[str, float]) -> dict[str, float]:
    """Min-max normalize a dict-of-floats; degenerate ranges return 0.5 everywhere."""

    if not values:
        return {}
    low = min(values.values())
    high = max(values.values())
    if high == low:
        return {key: 0.5 for key in values}
    return {key: (value - low) / (high - low) for key, value in values.items()}
