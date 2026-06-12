from api.app.schemas.optimizer import OptimizeRequest, SupplyMixResponse
from engine.fixtures import get_site
from engine.optimizer import optimize_supply_mix


def optimize_site_supply(request: OptimizeRequest) -> SupplyMixResponse:
    """Optimize the fixture power supply mix for a selected site."""

    site = get_site(request.cell_id)
    if site is None:
        raise KeyError(f"Unknown site cell: {request.cell_id}")
    return optimize_supply_mix(site, request)
