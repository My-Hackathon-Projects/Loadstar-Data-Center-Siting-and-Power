"""Health and assumptions endpoints."""

from fastapi import APIRouter

from backend.api.services.meta_service import get_assumptions, get_health
from backend.engine.contracts import AssumptionsResponse, HealthResponse

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return process health and active data mode."""

    return get_health()


@router.get("/assumptions", response_model=AssumptionsResponse)
def assumptions() -> AssumptionsResponse:
    """Return the public assumptions used by the fixture skeleton."""

    return get_assumptions()
