"""Pure-Python ranking and comparison logic for the site search endpoints."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal, cast

from backend.engine.assumptions import ASSUMPTIONS
from backend.engine.contracts import (
    CompareRequest,
    CompareResponse,
    RankedSite,
    ScaleWarning,
    ScoreExplanation,
    SearchRequest,
    SearchResponse,
    SiteFeature,
)
from backend.engine.fixtures import FEATURE_COLLECTION
from backend.engine.normalization import normalize_value, percentile_bounds

_Direction = Literal["lower_is_better", "higher_is_better", "composite"]


@dataclass(frozen=True)
class _ScoreFactor:
    name: str
    direction: _Direction
    score: Callable[[SiteFeature, Sequence[SiteFeature]], float]
    raw_value: Callable[[SiteFeature], str]


def _simple_factor(
    *,
    name: str,
    field_name: str,
    direction: _Direction,
    raw_value: Callable[[SiteFeature], str],
) -> _ScoreFactor:
    lower_is_better = direction == "lower_is_better"
    return _ScoreFactor(
        name=name,
        direction=direction,
        score=lambda site, candidates: _normalize(
            [float(getattr(candidate, field_name)) for candidate in candidates],
            float(getattr(site, field_name)),
            lower_is_better=lower_is_better,
        ),
        raw_value=raw_value,
    )


_SCORE_FACTORS: tuple[_ScoreFactor, ...] = (
    _simple_factor(
        name="price",
        field_name="mean_price_eur_mwh",
        direction="lower_is_better",
        raw_value=lambda site: f"{site.mean_price_eur_mwh:.0f} EUR/MWh",
    ),
    _simple_factor(
        name="carbon",
        field_name="carbon_intensity_g_kwh",
        direction="lower_is_better",
        raw_value=lambda site: f"{site.carbon_intensity_g_kwh:.0f} gCO2/kWh",
    ),
    _simple_factor(
        name="congestion",
        field_name="congestion_index",
        direction="lower_is_better",
        raw_value=lambda site: f"{site.congestion_index:.2f} congestion index",
    ),
    _simple_factor(
        name="grid",
        field_name="dist_hv_substation_km",
        direction="lower_is_better",
        raw_value=lambda site: f"{site.dist_hv_substation_km:.1f} km to HV substation",
    ),
    _ScoreFactor(
        name="connectivity",
        direction="composite",
        score=lambda site, candidates: _average(
            [
                _field_score(site, candidates, "dist_fiber_km", lower_is_better=True),
                _field_score(site, candidates, "dist_ixp_km", lower_is_better=True),
                _field_score(site, candidates, "latency_proxy_ms", lower_is_better=True),
            ]
        ),
        raw_value=lambda site: (
            f"{site.dist_fiber_km:.1f} km fiber / "
            f"{site.dist_ixp_km:.1f} km IXP / {site.latency_proxy_ms:.1f} ms"
        ),
    ),
    _ScoreFactor(
        name="land",
        direction="composite",
        score=lambda site, candidates: _average(
            [
                _field_score(site, candidates, "buildable_fraction", lower_is_better=False),
                _field_score(site, candidates, "dc_similarity", lower_is_better=False),
            ]
        ),
        raw_value=lambda site: (
            f"{site.buildable_fraction:.0%} buildable / "
            f"{site.dc_similarity:.0%} data-center similarity"
        ),
    ),
    _simple_factor(
        name="ml",
        field_name="lightgbm_score",
        direction="higher_is_better",
        raw_value=lambda site: f"{site.lightgbm_score:.0%} ML viability",
    ),
)


def _scale_warnings(power_mw: float) -> list[ScaleWarning]:
    bands = cast(dict[str, object], ASSUMPTIONS["scale_bands"])
    small_threshold = _assumption_float(bands["small_mw_threshold"])
    large_threshold = _assumption_float(bands["large_mw_threshold"])
    small_warning = _assumption_string(bands["small_warning"])
    large_warning = _assumption_string(bands["large_warning"])
    warnings: list[ScaleWarning] = []
    if power_mw < small_threshold:
        warnings.append(ScaleWarning(code="small_load", message=small_warning))
    if power_mw > large_threshold:
        warnings.append(ScaleWarning(code="large_load", message=large_warning))
    return warnings


def _normalize(values: Sequence[float], value: float, lower_is_better: bool) -> float:
    return normalize_value(
        value,
        percentile_bounds(values),
        lower_is_better=lower_is_better,
    )


def _field_score(
    site: SiteFeature,
    candidates: Sequence[SiteFeature],
    field_name: str,
    *,
    lower_is_better: bool,
) -> float:
    return _normalize(
        [float(getattr(candidate, field_name)) for candidate in candidates],
        float(getattr(site, field_name)),
        lower_is_better=lower_is_better,
    )


def _average(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _score_site(
    site: SiteFeature,
    candidates: Sequence[SiteFeature],
    request: SearchRequest,
) -> RankedSite:
    weights = cast(dict[str, float], request.weights.model_dump())
    breakdown: dict[str, float] = {}
    contributions: dict[str, float] = {}
    explanations: list[ScoreExplanation] = []

    for factor in _SCORE_FACTORS:
        score = round(factor.score(site, candidates), 4)
        weight = float(weights[factor.name])
        contribution = round(score * weight, 4)
        breakdown[factor.name] = score
        contributions[factor.name] = contribution
        explanations.append(
            ScoreExplanation(
                factor=factor.name,
                score=score,
                weight=weight,
                contribution=contribution,
                raw_value=factor.raw_value(site),
                direction=factor.direction,
            )
        )

    composite = round(sum(contributions.values()), 4)
    return RankedSite(
        site=site,
        composite_score=composite,
        score_breakdown=breakdown,
        score_contributions=contributions,
        score_explanations=explanations,
    )


def eligible_sites(
    request: SearchRequest,
    sites: Sequence[SiteFeature] | None = None,
) -> list[SiteFeature]:
    """Return fixture sites that pass country, exclusion, and headroom filters."""

    countries = {country.upper() for country in request.country_filter or []}
    source_sites = FEATURE_COLLECTION if sites is None else sites
    return [
        site
        for site in source_sites
        if not site.exclusion_flag
        and site.headroom_mw >= request.power_mw
        and (not countries or site.country_code in countries)
    ]


def search_sites(
    request: SearchRequest,
    sites: Sequence[SiteFeature] | None = None,
) -> SearchResponse:
    """Rank fixture sites using transparent normalized feature scoring."""

    candidates = eligible_sites(request, sites)

    ranked = sorted(
        (_score_site(site, candidates, request) for site in candidates),
        key=lambda result: (
            -result.composite_score,
            result.site.mean_price_eur_mwh,
            result.site.cell_id,
        ),
    )

    return SearchResponse(
        requested_power_mw=request.power_mw,
        workload_type=request.workload_type,
        warnings=_scale_warnings(request.power_mw),
        results=ranked[: request.top_k],
    )


def compare_sites(
    request: CompareRequest,
    sites: Sequence[SiteFeature] | None = None,
) -> CompareResponse:
    """Return fixture sites in the requested comparison order."""

    sites_by_id = {site.cell_id: site for site in (FEATURE_COLLECTION if sites is None else sites)}
    selected_sites: list[SiteFeature] = []
    for cell_id in request.cell_ids:
        site = sites_by_id.get(cell_id)
        if site is None:
            raise KeyError(f"Unknown site cell: {cell_id}")
        selected_sites.append(site)
    return CompareResponse(sites=selected_sites)


def _assumption_float(value: object) -> float:
    if isinstance(value, bool):
        raise TypeError("Expected numeric assumption.")
    if isinstance(value, int | float):
        return float(value)
    raise TypeError("Expected numeric assumption.")


def _assumption_string(value: object) -> str:
    if isinstance(value, str):
        return value
    raise TypeError("Expected string assumption.")
