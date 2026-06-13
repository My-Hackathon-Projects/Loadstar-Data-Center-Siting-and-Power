"""Supply-mix optimization endpoint."""

from typing import Any

from fastapi import APIRouter

from backend.api.routers.errors import key_error_message, not_found, unprocessable
from backend.api.services.optimizer_service import optimize_site_supply
from backend.engine.contracts import ApiErrorResponse, OptimizeRequest, SupplyMixResponse

router = APIRouter(prefix="/optimize", tags=["optimizer"])
OPTIMIZER_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ApiErrorResponse},
    422: {"model": ApiErrorResponse},
}


@router.post(
    "/supply-mix",
    response_model=SupplyMixResponse,
    responses=OPTIMIZER_ERROR_RESPONSES,
)
def optimize(request: OptimizeRequest) -> SupplyMixResponse:
    """Return a chart-ready single-site supply-mix optimization response."""

    try:
        return optimize_site_supply(request)
    except KeyError as exc:
        raise not_found(key_error_message(exc), code="site_not_found") from exc
    except RuntimeError as exc:
        raise unprocessable(str(exc), code="optimization_infeasible") from exc
