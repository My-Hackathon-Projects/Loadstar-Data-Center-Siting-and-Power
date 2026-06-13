"""Public supply-optimizer facade."""

from backend.engine.contracts import OptimizeRequest, ParetoPoint, SiteFeature, SupplyMixResponse
from backend.engine.optimizer_constants import DEFAULT_FRONTIER_POINTS
from backend.engine.optimizer_model import build_inputs, solve_supply_lp
from backend.engine.optimizer_outputs import build_pareto_point, build_supply_mix_response


def optimize_supply_mix(site: SiteFeature, request: OptimizeRequest) -> SupplyMixResponse:
    """Optimize a single site's supply mix and return chart-ready metrics."""

    recommended = solve_supply_lp(build_inputs(site, request, request.carbon_cap_g_kwh))
    frontier = _solve_pareto_frontier(site, request)
    return build_supply_mix_response(site, request, recommended, frontier)


def _solve_pareto_frontier(site: SiteFeature, request: OptimizeRequest) -> list[ParetoPoint]:
    points: list[ParetoPoint] = []
    for cap in _frontier_caps(site, request.carbon_cap_g_kwh):
        try:
            solution = solve_supply_lp(build_inputs(site, request, cap))
        except RuntimeError:
            continue
        points.append(build_pareto_point(cap, solution))

    if len(points) < 2:
        raise RuntimeError("Could not build a feasible optimizer Pareto frontier.")
    return points[:DEFAULT_FRONTIER_POINTS]


def _frontier_caps(site: SiteFeature, requested_cap: float | None) -> list[float | None]:
    carbon = max(site.carbon_intensity_g_kwh, 1.0)
    factors = (0.95, 0.85, 0.75, 0.65, 0.55, 0.45, 0.35, 0.28, 0.22)
    caps: list[float | None] = [None, *(round(carbon * factor, 3) for factor in factors)]
    if requested_cap is not None and requested_cap not in caps:
        caps.insert(1, requested_cap)
    return caps
