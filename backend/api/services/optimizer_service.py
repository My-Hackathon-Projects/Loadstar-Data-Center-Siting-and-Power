"""HTTP wrapper around engine.optimizer for the supply-mix endpoint.

Caches deterministic results in `result_cache.LruResultCache` so a re-run of
an identical request (same site, same load, same load profile, same carbon
cap) skips the LP solve. Cache misses log `solve_ms` so any future regression
is visible in the structured logs.
"""

from __future__ import annotations

import logging
import time

from backend.api.repositories.site_repository import site_repository
from backend.api.services.cache_keys import build_cache_key
from backend.api.services.result_cache import get_result_cache
from backend.engine.contracts import OptimizeRequest, SupplyMixResponse
from backend.engine.optimizer import optimize_supply_mix

logger = logging.getLogger("loadstar.optimizer")


def optimize_site_supply(request: OptimizeRequest) -> SupplyMixResponse:
    """Optimize the fixture power supply mix for a selected site, cached."""

    site = site_repository.get_site(request.cell_id)
    if site is None:
        raise KeyError(f"Unknown site cell: {request.cell_id}")

    cache = get_result_cache()
    cache_key = build_cache_key("optimize.supply_mix", request, site)
    cached = cache.get(cache_key)
    if cached is not None:
        logger.info(
            "optimize.cache_hit",
            extra={
                "event": "optimize.solved",
                "cell_id": request.cell_id,
                "load_mw": request.load_mw,
                "load_profile": request.load_profile,
                "cache_hit": True,
                "cache_key": cache_key,
            },
        )
        return cached.model_copy(update={"cache_key": cache_key})

    started = time.perf_counter()
    response = optimize_supply_mix(site, request)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    response_with_key = response.model_copy(update={"cache_key": cache_key})
    cache.set(cache_key, response_with_key)
    logger.info(
        "optimize.solved",
        extra={
            "event": "optimize.solved",
            "cell_id": request.cell_id,
            "load_mw": request.load_mw,
            "load_profile": request.load_profile,
            "pareto_points": len(response_with_key.pareto_frontier),
            "solver_status": response_with_key.solver_status,
            "solve_ms": elapsed_ms,
            "cache_hit": False,
            "cache_key": cache_key,
        },
    )
    return response_with_key
