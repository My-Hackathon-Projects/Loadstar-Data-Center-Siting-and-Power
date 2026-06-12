"""Issue 8: build per-cell ranking features from the subset artifacts.

Reads `hourly_carbon_subset.json`, `pypsa_clustered_opf.json`, and the
Ember congestion layers; produces `site_features_subset.json` with
normalized score inputs (5/95 percentile clip, not min-max), the
blended congestion index, and explicit missing-data flags for any
fallback source.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal, cast

import typer

from backend.engine.contracts import SiteFeature
from backend.pipeline.artifacts import (
    ArtifactSummary,
    display_path,
    upsert_source_artifacts,
    write_json_artifact,
)
from backend.pipeline.subset_ingestion import (
    DEFAULT_COUNTRIES,
    FIXTURE_SITES,
    parse_countries,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "loadstar.site_features.v1"
ARTIFACT_VERSION = "site-features-v1"
DETERMINISTIC_SEED = 20260612
CLIP_LOWER_PERCENTILE = 5.0
CLIP_UPPER_PERCENTILE = 95.0

Direction = Literal["higher", "lower"]

FEATURE_DIRECTIONS: dict[str, Direction] = {
    "mean_price_eur_mwh": "lower",
    "price_volatility": "lower",
    "carbon_intensity_g_kwh": "lower",
    "congestion_index": "lower",
    "headroom_mw": "higher",
    "dist_hv_substation_km": "lower",
    "dist_fiber_km": "lower",
    "dist_ixp_km": "lower",
    "latency_proxy_ms": "lower",
    "solar_cf": "higher",
    "wind_cf": "higher",
    "water_dist_km": "lower",
    "cooling_degree_proxy": "lower",
    "buildable_fraction": "higher",
}

CONGESTION_BLEND_WEIGHTS: dict[str, float] = {
    "ember_hub_country": 0.45,
    "opf_line_loading": 0.35,
    "opf_nodal_price_spread": 0.20,
}

app = typer.Typer(add_completion=False, help="Build subset per-cell ranking features.")


@dataclass(frozen=True)
class FeatureEngineeringResult:
    countries: tuple[str, ...]
    output_path: Path
    metadata_database: Path
    record_count: int
    checksum_sha256: str


def run_feature_engineering(
    countries: str | Sequence[str] = DEFAULT_COUNTRIES,
    input_dir: Path = ROOT_DIR / "data" / "processed" / "subset",
    output_dir: Path = ROOT_DIR / "data" / "processed" / "subset",
    metadata_database: Path = ROOT_DIR / "data" / "processed" / "source_artifacts.db",
) -> FeatureEngineeringResult:
    country_codes = parse_countries(countries)
    sites = _sites_for_countries(country_codes)
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    context = _load_context(input_dir)
    raw_records = [_raw_feature_record(site, context) for site in sites]
    normalized = _normalized_score_inputs(raw_records)
    records = [
        _final_feature_record(raw_record, normalized[index], context)
        for index, raw_record in enumerate(raw_records)
    ]

    output_path = output_dir / "site_features_subset.json"
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_version": ARTIFACT_VERSION,
        "deterministic_seed": DETERMINISTIC_SEED,
        "generated_at": generated_at,
        "countries": list(country_codes),
        "normalization": {
            "method": "percentile_clipping",
            "lower_percentile": CLIP_LOWER_PERCENTILE,
            "upper_percentile": CLIP_UPPER_PERCENTILE,
            "directions": FEATURE_DIRECTIONS,
        },
        "congestion_blend_weights": CONGESTION_BLEND_WEIGHTS,
        "source_context": context.summary,
        "records": records,
    }
    checksum = write_json_artifact(output_path, payload)
    summary = ArtifactSummary(
        name="site_features_subset",
        source="Loadstar subset feature engineering",
        status="processed",
        source_status="generated",
        path=display_path(output_path, ROOT_DIR),
        checksum_sha256=checksum,
        artifact_version=ARTIFACT_VERSION,
        record_count=len(records),
        fallback=None,
        notes="Per-cell ranking features with normalized score inputs and missing-data flags.",
    )
    upsert_source_artifacts(
        metadata_database=metadata_database,
        countries=country_codes,
        generated_at=generated_at,
        artifacts=[summary],
    )
    return FeatureEngineeringResult(
        countries=country_codes,
        output_path=output_path,
        metadata_database=metadata_database,
        record_count=len(records),
        checksum_sha256=checksum,
    )


@dataclass(frozen=True)
class FeatureContext:
    hourly_carbon_by_country: dict[str, float]
    hourly_carbon_method: str
    ember_country_congestion: dict[str, float]
    ember_hub_congestion: dict[str, float]
    line_loading_by_cell: dict[str, float]
    nodal_price_spread_by_cell: dict[str, float]
    summary: dict[str, object]


def _load_context(input_dir: Path) -> FeatureContext:
    hourly_payload = _load_payload(input_dir / "hourly_carbon_subset.json")
    opf_payload = _load_payload(input_dir / "pypsa_clustered_opf.json")
    congestion_payload = _load_payload(input_dir / "ember_grids_congestion_layers.json")
    hourly_records = _records(hourly_payload)
    opf_records = _records(opf_payload)
    congestion_records = _records(congestion_payload)
    active_method = _optional_string(hourly_payload.get("active_method"), "missing")

    line_loading_by_cell, nodal_price_spread_by_cell = _opf_components(opf_records)
    country_congestion, hub_congestion = _congestion_components(congestion_records)
    summary: dict[str, object] = {
        "hourly_carbon_artifact": _payload_status(hourly_payload),
        "opf_artifact": _payload_status(opf_payload),
        "congestion_artifact": _payload_status(congestion_payload),
    }
    return FeatureContext(
        hourly_carbon_by_country=_average_hourly_carbon(hourly_records),
        hourly_carbon_method=active_method,
        ember_country_congestion=country_congestion,
        ember_hub_congestion=hub_congestion,
        line_loading_by_cell=line_loading_by_cell,
        nodal_price_spread_by_cell=nodal_price_spread_by_cell,
        summary=summary,
    )


def _raw_feature_record(site: SiteFeature, context: FeatureContext) -> dict[str, object]:
    carbon = context.hourly_carbon_by_country.get(site.country_code, site.carbon_intensity_g_kwh)
    ember_component = _ember_congestion(site, context)
    line_component = context.line_loading_by_cell.get(site.cell_id, site.congestion_index)
    nodal_component = context.nodal_price_spread_by_cell.get(site.cell_id, site.congestion_index)
    blended_congestion = _clamp01(
        CONGESTION_BLEND_WEIGHTS["ember_hub_country"] * ember_component
        + CONGESTION_BLEND_WEIGHTS["opf_line_loading"] * line_component
        + CONGESTION_BLEND_WEIGHTS["opf_nodal_price_spread"] * nodal_component
    )
    return {
        "cell_id": site.cell_id,
        "country_code": site.country_code,
        "region_name": site.region_name,
        "latitude": site.latitude,
        "longitude": site.longitude,
        "resolution": site.resolution,
        "mean_price_eur_mwh": site.mean_price_eur_mwh,
        "price_volatility": site.price_volatility,
        "carbon_intensity_g_kwh": round(carbon, 3),
        "congestion_index": round(blended_congestion, 4),
        "headroom_mw": site.headroom_mw,
        "dist_hv_substation_km": site.dist_hv_substation_km,
        "dist_fiber_km": site.dist_fiber_km,
        "dist_ixp_km": site.dist_ixp_km,
        "latency_proxy_ms": site.latency_proxy_ms,
        "solar_cf": site.solar_cf,
        "wind_cf": site.wind_cf,
        "water_dist_km": site.water_dist_km,
        "cooling_degree_proxy": site.cooling_degree_proxy,
        "buildable_fraction": site.buildable_fraction,
        "dc_similarity": site.dc_similarity,
        "lightgbm_score": site.lightgbm_score,
        "exclusion_flag": site.exclusion_flag,
        "congestion_components": {
            "ember_hub_country": round(ember_component, 4),
            "opf_line_loading": round(line_component, 4),
            "opf_nodal_price_spread": round(nodal_component, 4),
        },
        "missing_data_flags": {
            "entsoe_hourly_generation_mix": context.hourly_carbon_method
            != "entsoe_hourly_generation_mix",
            "bbmaps_fiber": True,
            "official_osm_extracts": True,
            "official_ember_grids": True,
            "full_pypsa_opf": True,
        },
        "source_methods": {
            "carbon": context.hourly_carbon_method,
            "congestion": "ember_hub_country_plus_precomputed_opf_proxy",
            "fiber": "ixp_proxy_fallback",
            "land": "fixture_schema_compatible_proxy",
        },
    }


def _final_feature_record(
    raw_record: dict[str, object],
    normalized_score_inputs: dict[str, float],
    context: FeatureContext,
) -> dict[str, object]:
    record = dict(raw_record)
    record["normalized_score_inputs"] = normalized_score_inputs
    record["map_overlay_values"] = {
        "price": normalized_score_inputs["mean_price_eur_mwh"],
        "carbon": normalized_score_inputs["carbon_intensity_g_kwh"],
        "congestion": normalized_score_inputs["congestion_index"],
        "headroom": normalized_score_inputs["headroom_mw"],
        "substation": normalized_score_inputs["dist_hv_substation_km"],
        "fiber_or_ixp": min(
            normalized_score_inputs["dist_fiber_km"],
            normalized_score_inputs["dist_ixp_km"],
        ),
        "renewables": round(
            (
                normalized_score_inputs["solar_cf"]
                + normalized_score_inputs["wind_cf"]
            )
            / 2,
            4,
        ),
        "water": normalized_score_inputs["water_dist_km"],
        "cooling": normalized_score_inputs["cooling_degree_proxy"],
        "exclusion": 0.0 if bool(raw_record["exclusion_flag"]) else 1.0,
    }
    record["feature_version"] = ARTIFACT_VERSION
    record["carbon_method_visible"] = context.hourly_carbon_method
    return record


def _normalized_score_inputs(records: Sequence[dict[str, object]]) -> list[dict[str, float]]:
    # Use 5/95 percentile clipping rather than straight min-max so a single
    # outlier (a malformed cell or a fixture edge case) cannot dominate the
    # normalized scale. The clip + linear rescale preserves rank order on the
    # bulk of the distribution.
    values_by_feature: dict[str, list[float]] = {
        feature: [_required_float(record[feature], feature) for record in records]
        for feature in FEATURE_DIRECTIONS
    }
    bounds = {
        feature: (
            _percentile(values, CLIP_LOWER_PERCENTILE),
            _percentile(values, CLIP_UPPER_PERCENTILE),
        )
        for feature, values in values_by_feature.items()
    }
    normalized_records: list[dict[str, float]] = []
    for record in records:
        normalized: dict[str, float] = {}
        for feature, direction in FEATURE_DIRECTIONS.items():
            low, high = bounds[feature]
            value = _required_float(record[feature], feature)
            if high == low:
                score = 0.5
            else:
                clipped = min(max(value, low), high)
                score = (clipped - low) / (high - low)
                if direction == "lower":
                    score = 1 - score
            normalized[feature] = round(_clamp01(score), 4)
        normalized_records.append(normalized)
    return normalized_records


def _opf_components(
    opf_records: Sequence[dict[str, object]],
) -> tuple[dict[str, float], dict[str, float]]:
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
            loading = _optional_float(item_dict.get("loading_percent"))
            if loading is None:
                continue
            for key in ("from_cell_id", "to_cell_id"):
                cell_id = item_dict.get(key)
                if isinstance(cell_id, str):
                    line_values.setdefault(cell_id, []).append(_clamp01(loading / 100))
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
            price = _optional_float(item_dict.get("nodal_price_eur_mwh"))
            if isinstance(cell_id, str) and price is not None:
                nodal_prices[cell_id] = price
    nodal_spread = _minmax(nodal_prices)
    return line_loading_by_cell, nodal_spread


def _congestion_components(
    congestion_records: Sequence[dict[str, object]],
) -> tuple[dict[str, float], dict[str, float]]:
    country: dict[str, float] = {}
    hub: dict[str, float] = {}
    for record in congestion_records:
        layer_type = record.get("layer_type")
        if layer_type == "country_summary":
            country_code = record.get("country_code")
            value = _optional_float(record.get("mean_congestion_index"))
            if isinstance(country_code, str) and value is not None:
                country[country_code] = value
        elif layer_type == "hub_proxy":
            cell_id = record.get("cell_id")
            value = _optional_float(record.get("congestion_index"))
            if isinstance(cell_id, str) and value is not None:
                hub[cell_id] = value
    return country, hub


def _ember_congestion(site: SiteFeature, context: FeatureContext) -> float:
    hub = context.ember_hub_congestion.get(site.cell_id, site.congestion_index)
    country = context.ember_country_congestion.get(site.country_code, site.congestion_index)
    return _clamp01(0.6 * hub + 0.4 * country)


def _average_hourly_carbon(records: Sequence[dict[str, object]]) -> dict[str, float]:
    values: dict[str, list[float]] = {}
    for record in records:
        zone_id = record.get("zone_id")
        carbon = _optional_float(record.get("carbon_g_kwh"))
        if isinstance(zone_id, str) and carbon is not None:
            values.setdefault(zone_id, []).append(carbon)
    return {zone_id: sum(items) / len(items) for zone_id, items in values.items()}


def _load_payload(path: Path) -> dict[str, object]:
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
    raw = payload.get("records")
    if not isinstance(raw, list):
        return []
    records: list[dict[str, object]] = []
    for item in cast(list[object], raw):
        if isinstance(item, dict):
            records.append(cast(dict[str, object], item))
    return records


def _payload_status(payload: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": _optional_string(payload.get("schema_version"), "missing"),
        "artifact_version": _optional_string(payload.get("artifact_version"), "missing"),
        "source_status": _optional_string(payload.get("source_status"), "missing"),
        "active_method": _optional_string(payload.get("active_method"), "not_applicable"),
    }


def _minmax(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    low = min(values.values())
    high = max(values.values())
    if high == low:
        return {key: 0.5 for key in values}
    return {key: (value - low) / (high - low) for key, value in values.items()}


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        raise ValueError("Cannot compute percentile of an empty sequence.")
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * percentile / 100
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    fraction = position - lower_index
    return sorted_values[lower_index] + (
        sorted_values[upper_index] - sorted_values[lower_index]
    ) * fraction


def _sites_for_countries(countries: Sequence[str]) -> list[SiteFeature]:
    country_set = set(countries)
    sites = [site for site in FIXTURE_SITES if site.country_code in country_set]
    if not sites:
        raise ValueError(f"No fixture cells exist for requested countries: {', '.join(countries)}")
    return sites


def _required_float(value: object, field_name: str) -> float:
    parsed = _optional_float(value)
    if parsed is None:
        raise ValueError(f"Expected numeric field {field_name}.")
    return parsed


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _optional_string(value: object, default: str) -> str:
    return value if isinstance(value, str) and value else default


def _clamp01(value: float) -> float:
    return min(max(value, 0.0), 1.0)


@app.callback(invoke_without_command=True)
def main(
    countries: Annotated[
        str,
        typer.Option("--countries", help="Comma-separated ISO-3166 alpha-2 countries."),
    ] = ",".join(DEFAULT_COUNTRIES),
    input_dir: Annotated[
        Path,
        typer.Option("--input-dir", help="Directory containing subset artifacts."),
    ] = ROOT_DIR / "data" / "processed" / "subset",
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", help="Directory for processed feature artifacts."),
    ] = ROOT_DIR / "data" / "processed" / "subset",
    metadata_database: Annotated[
        Path,
        typer.Option("--metadata-database", help="SQLite source_artifacts metadata database."),
    ] = ROOT_DIR / "data" / "processed" / "source_artifacts.db",
) -> None:
    result = run_feature_engineering(
        countries=countries,
        input_dir=input_dir,
        output_dir=output_dir,
        metadata_database=metadata_database,
    )
    typer.echo(f"Wrote site features artifact: {result.output_path}")
    typer.echo(f"Updated source_artifacts metadata: {result.metadata_database}")
    typer.echo(
        f"- records={result.record_count}; checksum={result.checksum_sha256[:12]}"
    )


if __name__ == "__main__":
    app()
