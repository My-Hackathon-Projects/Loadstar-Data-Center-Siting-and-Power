"""HTTP wrapper around engine.optimizer for the supply-mix endpoint."""

from backend.api.repositories.site_repository import site_repository
from backend.engine.contracts import OptimizeRequest, SupplyMixResponse
from backend.engine.optimizer import optimize_supply_mix

from .cache_keys import build_cache_key


def optimize_site_supply(request: OptimizeRequest) -> SupplyMixResponse:
    """Optimize the fixture power supply mix for a selected site."""

    site = site_repository.get_site(request.cell_id)
    if site is None:
        raise KeyError(f"Unknown site cell: {request.cell_id}")
    response = optimize_supply_mix(site, request)
    return response.model_copy(
        update={"cache_key": build_cache_key("optimize.supply_mix", request, site)}
    )
