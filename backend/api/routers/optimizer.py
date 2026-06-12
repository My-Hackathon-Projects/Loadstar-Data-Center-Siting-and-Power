"""Supply-mix optimization endpoint."""

from fastapi import APIRouter, HTTPException

from backend.api.services.optimizer_service import optimize_site_supply
from backend.engine.contracts import OptimizeRequest, SupplyMixResponse

router = APIRouter(prefix="/optimize", tags=["optimizer"])


@router.post("/supply-mix", response_model=SupplyMixResponse)
def optimize(request: OptimizeRequest) -> SupplyMixResponse:
    """Return a chart-ready fixture supply-mix optimization response."""

    try:
        return optimize_site_supply(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
