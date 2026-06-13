"""Feature record assembly + percentile-clip normalization.

Given a `FeatureContext` from `_feature_context.py` and the canonical
`SiteFeature`, build the raw and final per-cell rows that land in
`site_features_subset.json`. Normalization uses percentile clipping so a
single outlier cell cannot dominate the rescale.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from backend.engine.assumptions import ASSUMPTIONS
from backend.engine.contracts import SiteFeature
from backend.engine.normalization import normalize_value, percentile_bounds
from backend.pipeline._feature_context import FeatureContext
from backend.pipeline._value_parsers import clamp01, required_float

# Single source of truth for the percentile-clip bounds and the method label
# stamped into the artifact. The same numbers feed the API's score normalizer.
_NORMALIZATION = ASSUMPTIONS["scoring_normalization"]
NORMALIZATION_METHOD: str = _NORMALIZATION["method"]
CLIP_LOWER_PERCENTILE: float = float(_NORMALIZATION["lower_percentile"])
CLIP_UPPER_PERCENTILE: float = float(_NORMALIZATION["upper_percentile"])


Direction = Literal["higher", "lower"]


# Whether higher or lower raw values are preferred when normalizing each
# searchable feature. Used in scoring + map overlays.
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


# Three-way blend that produces the final congestion_index per cell. Sums to 1.0.
CONGESTION_BLEND_WEIGHTS: dict[str, float] = {
    "ember_hub_country": 0.45,
    "opf_line_loading": 0.35,
    "opf_nodal_price_spread": 0.20,
}


def raw_feature_record(site: SiteFeature, context: FeatureContext) -> dict[str, object]:
    """Per-cell row before normalization: blended congestion, source methods, flags."""

    carbon = context.hourly_carbon_by_country.get(site.country_code, site.carbon_intensity_g_kwh)
    land = context.land_by_cell.get(site.cell_id, {})
    model = context.model_by_cell.get(site.cell_id)
    price_profile = context.price_by_country.get(site.country_code)
    mean_price = (
        price_profile.mean_price_eur_mwh if price_profile is not None else site.mean_price_eur_mwh
    )
    price_volatility = (
        price_profile.price_volatility if price_profile is not None else site.price_volatility
    )
    price_method = (
        price_profile.source_method if price_profile is not None else "fixture_static_price"
    )
    ember_component = _ember_congestion(site, context)
    line_component = context.line_loading_by_cell.get(site.cell_id, site.congestion_index)
    nodal_component = context.nodal_price_spread_by_cell.get(site.cell_id, site.congestion_index)
    blended_congestion = clamp01(
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
        "mean_price_eur_mwh": round(mean_price, 2),
        "price_volatility": round(price_volatility, 2),
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
        "buildable_fraction": land.get("buildable_fraction", site.buildable_fraction),
        "dc_similarity": land.get("dc_similarity", site.dc_similarity),
        "lightgbm_score": model.viability_score if model else site.lightgbm_score,
        "shap_values": model.shap_values if model else site.shap_values,
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
            "alphaearth_land": context.land_source_status != "earth_engine",
            "siting_model": context.model_source_status != "trained",
            "ember_hourly_price": context.price_method != "ember_csv_local_db",
        },
        "source_methods": {
            "carbon": context.hourly_carbon_method,
            "congestion": "ember_hub_country_plus_precomputed_opf_proxy",
            "fiber": "ixp_proxy_fallback",
            "land": context.land_method,
            "ml": context.model_method,
            "price": price_method,
        },
    }


def final_feature_record(
    raw_record: dict[str, object],
    normalized_score_inputs: dict[str, float],
    context: FeatureContext,
    artifact_version: str,
) -> dict[str, object]:
    """Add normalized score inputs + the seven map overlay channels."""

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
            (normalized_score_inputs["solar_cf"] + normalized_score_inputs["wind_cf"]) / 2,
            4,
        ),
        "water": normalized_score_inputs["water_dist_km"],
        "cooling": normalized_score_inputs["cooling_degree_proxy"],
        "exclusion": 0.0 if bool(raw_record["exclusion_flag"]) else 1.0,
    }
    record["feature_version"] = artifact_version
    record["carbon_method_visible"] = context.hourly_carbon_method
    return record


def normalized_score_inputs(
    records: Sequence[dict[str, object]],
) -> list[dict[str, float]]:
    """Apply 5/95 percentile-clip normalization across all records.

    Using percentile clipping rather than straight min-max prevents a single
    outlier (a malformed cell or a fixture edge case) from dominating the
    normalized scale. The clip + linear rescale preserves rank order on the
    bulk of the distribution.
    """

    values_by_feature: dict[str, list[float]] = {
        feature: [required_float(record[feature], feature) for record in records]
        for feature in FEATURE_DIRECTIONS
    }
    bounds = {
        feature: percentile_bounds(
            values,
            lower_percentile=CLIP_LOWER_PERCENTILE,
            upper_percentile=CLIP_UPPER_PERCENTILE,
        )
        for feature, values in values_by_feature.items()
    }
    normalized_records: list[dict[str, float]] = []
    for record in records:
        normalized: dict[str, float] = {}
        for feature, direction in FEATURE_DIRECTIONS.items():
            value = required_float(record[feature], feature)
            score = normalize_value(
                value,
                bounds[feature],
                lower_is_better=direction == "lower",
                degenerate_score=0.5,
            )
            normalized[feature] = round(clamp01(score), 4)
        normalized_records.append(normalized)
    return normalized_records


def _ember_congestion(site: SiteFeature, context: FeatureContext) -> float:
    """Blend per-hub and per-country Ember congestion into a single 0..1 value."""

    hub = context.ember_hub_congestion.get(site.cell_id, site.congestion_index)
    country = context.ember_country_congestion.get(site.country_code, site.congestion_index)
    return clamp01(0.6 * hub + 0.4 * country)
