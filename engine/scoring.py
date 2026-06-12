from engine.assumptions import ASSUMPTIONS
from engine.contracts import (
    CompareRequest,
    CompareResponse,
    RankedSite,
    ScaleWarning,
    SearchRequest,
    SearchResponse,
    SiteFeature,
)
from engine.fixtures import FEATURE_COLLECTION, get_site

LOWER_IS_BETTER_FIELDS = {
    "price": "mean_price_eur_mwh",
    "carbon": "carbon_intensity_g_kwh",
    "congestion": "congestion_index",
    "grid": "dist_hv_substation_km",
    "connectivity": "latency_proxy_ms",
}

HIGHER_IS_BETTER_FIELDS = {
    "land": "buildable_fraction",
    "ml": "lightgbm_score",
}


def _scale_warnings(power_mw: float) -> list[ScaleWarning]:
    bands = ASSUMPTIONS["scale_bands"]
    warnings: list[ScaleWarning] = []
    if power_mw < bands["small_mw_threshold"]:
        warnings.append(ScaleWarning(code="small_load", message=bands["small_warning"]))
    if power_mw > bands["large_mw_threshold"]:
        warnings.append(ScaleWarning(code="large_load", message=bands["large_warning"]))
    return warnings


def _normalize(values: list[float], value: float, lower_is_better: bool) -> float:
    low = min(values)
    high = max(values)
    if high == low:
        return 1.0
    normalized = (value - low) / (high - low)
    if lower_is_better:
        normalized = 1 - normalized
    return max(0.0, min(1.0, normalized))


def _score_site(
    site: SiteFeature,
    candidates: list[SiteFeature],
    request: SearchRequest,
) -> RankedSite:
    weights = request.weights.model_dump()
    breakdown: dict[str, float] = {}

    for score_name, field_name in LOWER_IS_BETTER_FIELDS.items():
        values = [getattr(candidate, field_name) for candidate in candidates]
        breakdown[score_name] = _normalize(values, getattr(site, field_name), lower_is_better=True)

    for score_name, field_name in HIGHER_IS_BETTER_FIELDS.items():
        values = [getattr(candidate, field_name) for candidate in candidates]
        breakdown[score_name] = _normalize(values, getattr(site, field_name), lower_is_better=False)

    composite = sum(breakdown[key] * weights[key] for key in breakdown)
    return RankedSite(site=site, composite_score=round(composite, 4), score_breakdown=breakdown)


def search_sites(request: SearchRequest) -> SearchResponse:
    """Rank fixture sites using transparent normalized feature scoring."""

    countries = {country.upper() for country in request.country_filter or []}
    candidates = [
        site
        for site in FEATURE_COLLECTION
        if not site.exclusion_flag
        and site.headroom_mw >= request.power_mw
        and (not countries or site.country_code in countries)
    ]

    ranked = sorted(
        (_score_site(site, candidates, request) for site in candidates),
        key=lambda result: result.composite_score,
        reverse=True,
    )

    return SearchResponse(
        requested_power_mw=request.power_mw,
        workload_type=request.workload_type,
        warnings=_scale_warnings(request.power_mw),
        results=ranked[: request.top_k],
    )


def compare_sites(request: CompareRequest) -> CompareResponse:
    """Return fixture sites in the requested comparison order."""

    sites: list[SiteFeature] = []
    for cell_id in request.cell_ids:
        site = get_site(cell_id)
        if site is None:
            raise KeyError(f"Unknown site cell: {cell_id}")
        sites.append(site)
    return CompareResponse(sites=sites)
