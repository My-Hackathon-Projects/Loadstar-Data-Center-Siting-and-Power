"""Pydantic v2 wire contracts for the Loadstar API.

Single source of truth for every request and response shape exposed at
`/sites/*`, `/optimize/*`, and `/layers/*`. Pipeline code also imports
`SiteFeature` from here so ingestion cannot drift from the API.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.engine.assumptions import DEFAULT_WEIGHTS


class ApiErrorDetail(BaseModel):
    code: str
    message: str


class ApiErrorResponse(BaseModel):
    detail: ApiErrorDetail


class HealthDependency(BaseModel):
    """Status of one dependency the API talks to (Postgres, Redis, ...)."""

    status: Literal["ok", "unreachable", "disabled"]
    detail: str | None = None
    latency_ms: float | None = None


class HealthDependencies(BaseModel):
    """Aggregate dependency status surfaced from `/health`."""

    postgres: HealthDependency
    redis: HealthDependency


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    data_mode: str
    cache_key: str
    # Below are additive fields. Existing clients (and the pre-Phase-2 test that
    # asserts only the three fields above) are unaffected because Pydantic v2
    # serializes optionals with defaults.
    version: str = "0.0.0"
    git_sha: str | None = None
    started_at: datetime | None = None
    uptime_seconds: float = 0.0
    dependencies: HealthDependencies | None = None


class AssumptionsResponse(BaseModel):
    data_mode: str
    cache_key: str
    assumptions: dict[str, Any]


class SourceArtifact(BaseModel):
    """One row from `source_artifacts.db` exposed via `/meta/source-artifacts`."""

    artifact_name: str
    country_scope: str
    artifact_version: str
    source_name: str
    source_status: str
    status: str
    checksum_sha256: str
    artifact_path: str
    record_count: int
    fallback: str | None = None
    generated_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceArtifactsResponse(BaseModel):
    """Operational metadata for the active data slice.

    `data_version` is a stable short fingerprint over the artifact checksums;
    consumers can use it to detect when ingestion has produced a new slice.
    """

    data_mode: str
    cache_key: str
    data_version: str
    artifact_count: int
    artifacts: list[SourceArtifact]


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
    # Optional grid-aware enrichment populated by `backend.pipeline.pypsa_network`
    # when the real PyPSA-Eur ingestion has run. Stays None on fixture-only
    # deployments so existing artifacts continue to validate.
    nearest_substation_kv: float | None = None
    nearest_substation_distance_km: float | None = None
    nearest_substation_capacity_mva: float | None = None


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
    cache_key: str = ""
    features: list[LayerFeature]


class SiteDetailResponse(BaseModel):
    data_mode: Literal["fixture"] = "fixture"
    cache_key: str = ""
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
    cache_key: str = ""
    requested_power_mw: float
    workload_type: str
    warnings: list[ScaleWarning]
    results: list[RankedSite]


class CompareRequest(BaseModel):
    cell_ids: list[str] = Field(min_length=2, max_length=5)


class CompareResponse(BaseModel):
    data_mode: Literal["fixture"] = "fixture"
    cache_key: str = ""
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
    backup_share: float
    curtailment_share: float


class SupplyMixResponse(BaseModel):
    data_mode: Literal["fixture"] = "fixture"
    cache_key: str = ""
    cell_id: str
    load_mw: float
    load_profile: str
    solver_status: str
    optimization_horizon_hours: int
    recommended_portfolio: dict[str, float]
    effective_cost_eur_mwh: float
    effective_carbon_g_kwh: float
    annual_matched_clean_share: float
    hourly_24_7_cfe_share: float
    pareto_frontier: list[ParetoPoint]
    dispatch_summary: dict[str, float]
    dispatch_preview: list[dict[str, float]]


JobStatus = Literal["pending", "running", "completed", "failed"]


class OptimizationJobAccepted(BaseModel):
    """Returned with HTTP 202 from `POST /optimize/supply-mix/async`."""

    job_id: str
    status_url: str
    status: JobStatus = "pending"
    cache_key: str


class OptimizationJobStatus(BaseModel):
    """Polled via `GET /optimize/jobs/{job_id}`. Mirrors `optimization_runs`."""

    job_id: str
    status: JobStatus
    cache_key: str
    request_id: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    solve_ms: float | None = None
    result: SupplyMixResponse | None = None
    error: ApiErrorDetail | None = None


ExplainSource = Literal["openai", "template"]


class ExplainRequest(BaseModel):
    """Payload for `POST /agent/explain`."""

    cell_id: str
    power_mw: float = Field(gt=0)
    workload_type: Literal["training", "inference", "mixed"] = "training"


class ExplainResponse(BaseModel):
    """Result of an agent explanation. Falls back to the template on any LLM error.

    `source` lets the UI render a "Live · gpt-4o-mini" pill versus a
    "Deterministic template" pill; both render the same chat bubble shape.
    """

    cell_id: str
    source: ExplainSource
    model: str | None = None
    message: str
    cache_key: str


class FredSpeechRequest(BaseModel):
    """Text Fred should speak through the configured ElevenLabs voice."""

    text: str = Field(min_length=1, max_length=1200)


class AgentChatTurn(BaseModel):
    """One recent chat turn sent back to Fred for conversational context."""

    speaker: Literal["assistant", "user"]
    body: str = Field(min_length=1, max_length=1200)


def _empty_agent_chat_history() -> list[AgentChatTurn]:
    return []


class AgentChatRequest(BaseModel):
    """Payload for `POST /agent/chat`. Fred responds to a free-text ask."""

    message: str
    power_mw: float = Field(gt=0)
    workload_type: Literal["training", "inference", "mixed"] = "training"
    selected_cell_id: str | None = None
    history: list[AgentChatTurn] = Field(
        default_factory=_empty_agent_chat_history,
        max_length=12,
    )


class AgentAction(BaseModel):
    """Structured dashboard action the chat asks the UI to apply.

    For a `search` action the UI writes `applied` into its store (which drives the
    existing search query) and flies the map to `focus_cell_id`. `none` leaves the
    dashboard untouched.
    """

    type: Literal["search", "none"] = "none"
    search: SearchResponse | None = None
    focus_cell_id: str | None = None
    applied: SearchRequest | None = None


class AgentChatResponse(BaseModel):
    """Result of an agent chat turn.

    The deterministic narration is the demo-safe default; a live LLM only
    rephrases the reply around the same engine-computed numbers. `source` drives
    the same "Live" vs "template" pill as the explain endpoint.
    """

    source: ExplainSource
    model: str | None = None
    message: str
    action: AgentAction
    cache_key: str = ""
