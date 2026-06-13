"""Pydantic v2 wire contracts for the Loadstar API.

Single source of truth for every request and response shape exposed at
`/sites/*`, `/optimize/*`, and `/layers/*`. Pipeline code also imports
`SiteFeature` from here so ingestion cannot drift from the API.
"""

from typing import Literal

from pydantic import BaseModel, Field

from backend.engine.assumptions import DEFAULT_WEIGHTS


class SiteFeature(BaseModel):
    cell_id: str
    country_code: str
    region_name: str
    latitude: float
    longitude: float
    resolution: int = 5
    mean_price_eur_mwh: float
    price_volatility: float
    carbon_intensity_g_kwh: float
    congestion_index: float = Field(ge=0, le=1)
    headroom_mw: float
    dist_hv_substation_km: float
    dist_fiber_km: float
    dist_ixp_km: float
    latency_proxy_ms: float
    solar_cf: float = Field(ge=0, le=1)
    wind_cf: float = Field(ge=0, le=1)
    water_dist_km: float
    cooling_degree_proxy: float
    buildable_fraction: float = Field(ge=0, le=1)
    dc_similarity: float = Field(ge=0, le=1)
    lightgbm_score: float = Field(ge=0, le=1)
    shap_values: dict[str, float]
    exclusion_flag: bool


class LayerFeatureProperties(SiteFeature):
    layer_name: str
    layer_value: float


class PointGeometry(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float]


class LayerFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: PointGeometry
    properties: LayerFeatureProperties


class LayerResponse(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[LayerFeature]


class SiteDetailResponse(BaseModel):
    data_mode: Literal["fixture"] = "fixture"
    site: SiteFeature


class Weights(BaseModel):
    price: float = DEFAULT_WEIGHTS["price"]
    carbon: float = DEFAULT_WEIGHTS["carbon"]
    congestion: float = DEFAULT_WEIGHTS["congestion"]
    grid: float = DEFAULT_WEIGHTS["grid"]
    connectivity: float = DEFAULT_WEIGHTS["connectivity"]
    land: float = DEFAULT_WEIGHTS["land"]
    ml: float = DEFAULT_WEIGHTS["ml"]


class SearchRequest(BaseModel):
    power_mw: float = Field(gt=0)
    workload_type: Literal["training", "inference", "mixed"] = "training"
    top_k: int = Field(default=10, ge=1, le=50)
    weights: Weights = Field(default_factory=Weights)
    country_filter: list[str] | None = None


class ScaleWarning(BaseModel):
    code: str
    message: str


class ScoreExplanation(BaseModel):
    factor: str
    score: float = Field(ge=0, le=1)
    weight: float
    contribution: float
    raw_value: str
    direction: Literal["lower_is_better", "higher_is_better", "composite"]


class RankedSite(BaseModel):
    site: SiteFeature
    composite_score: float
    score_breakdown: dict[str, float]
    score_contributions: dict[str, float]
    score_explanations: list[ScoreExplanation]


class SearchResponse(BaseModel):
    data_mode: Literal["fixture"] = "fixture"
    requested_power_mw: float
    workload_type: str
    warnings: list[ScaleWarning]
    results: list[RankedSite]


class CompareRequest(BaseModel):
    cell_ids: list[str] = Field(min_length=2, max_length=5)


class CompareResponse(BaseModel):
    data_mode: Literal["fixture"] = "fixture"
    sites: list[SiteFeature]


class OptimizeRequest(BaseModel):
    cell_id: str
    load_mw: float = Field(gt=0)
    carbon_cap_g_kwh: float | None = Field(default=None, ge=0)
    load_profile: Literal["flat_24_7", "spiky_training"] = "flat_24_7"


class ParetoPoint(BaseModel):
    carbon_cap_g_kwh: float | None
    effective_cost_eur_mwh: float
    effective_carbon_g_kwh: float
    grid_share: float
    wind_ppa_share: float
    solar_ppa_share: float
    onsite_solar_share: float
    battery_shifted_share: float


class SupplyMixResponse(BaseModel):
    data_mode: Literal["fixture"] = "fixture"
    cell_id: str
    load_mw: float
    load_profile: str
    recommended_portfolio: dict[str, float]
    effective_cost_eur_mwh: float
    effective_carbon_g_kwh: float
    annual_matched_clean_share: float
    hourly_24_7_cfe_share: float
    pareto_frontier: list[ParetoPoint]
    dispatch_preview: list[dict[str, float]]
