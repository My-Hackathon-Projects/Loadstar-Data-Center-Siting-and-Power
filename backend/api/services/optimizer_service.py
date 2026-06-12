"""HTTP wrapper around engine.optimizer for the supply-mix endpoint."""

from backend.engine.contracts import OptimizeRequest, SupplyMixResponse
from backend.engine.fixtures import get_site
from backend.engine.optimizer import optimize_supply_mix


def optimize_site_supply(request: OptimizeRequest) -> SupplyMixResponse:
    """Optimize the fixture power supply mix for a selected site."""

    site = get_site(request.cell_id)
    if site is None:
        raise KeyError(f"Unknown site cell: {request.cell_id}")
    return optimize_supply_mix(site, request)
