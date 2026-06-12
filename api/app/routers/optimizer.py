from fastapi import APIRouter, HTTPException

from api.app.schemas.optimizer import OptimizeRequest, SupplyMixResponse
from api.app.services.optimizer_service import optimize_site_supply

router = APIRouter(prefix="/optimize", tags=["optimizer"])


@router.post("/supply-mix", response_model=SupplyMixResponse)
def optimize(request: OptimizeRequest) -> SupplyMixResponse:
    """Return a chart-ready fixture supply-mix optimization response."""

    try:
        return optimize_site_supply(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
