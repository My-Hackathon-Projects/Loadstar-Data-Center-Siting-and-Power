"""Service layer for the meta endpoints."""

from backend.api.core.config import get_settings
from backend.api.services.cache_keys import build_cache_key
from backend.engine.assumptions import ASSUMPTIONS
from backend.engine.contracts import AssumptionsResponse, HealthResponse


def get_health() -> HealthResponse:
    """Return process health and active data mode."""

    data_mode = get_settings().data_mode
    return HealthResponse(
        data_mode=data_mode,
        cache_key=build_cache_key("health", data_mode),
    )


def get_assumptions() -> AssumptionsResponse:
    """Return public assumptions for API consumers."""

    data_mode = get_settings().data_mode
    return AssumptionsResponse(
        data_mode=data_mode,
        cache_key=build_cache_key("assumptions", data_mode, ASSUMPTIONS),
        assumptions=ASSUMPTIONS,
    )
