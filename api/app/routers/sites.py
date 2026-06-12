from fastapi import APIRouter, HTTPException

from api.app.schemas.sites import (
    CompareRequest,
    CompareResponse,
    LayerResponse,
    SearchRequest,
    SearchResponse,
    SiteDetailResponse,
)
from api.app.services.site_service import (
    compare_site_cells,
    get_layer,
    get_site_detail,
    search_site_cells,
)

router = APIRouter(tags=["sites"])


@router.get("/layers/{layer_name}", response_model=LayerResponse)
def layer(layer_name: str) -> LayerResponse:
    """Return a GeoJSON layer for the requested fixture feature."""

    try:
        return get_layer(layer_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sites/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    """Rank fixture sites for a requested load size."""

    return search_site_cells(request)


@router.get("/sites/{cell_id}", response_model=SiteDetailResponse)
def site_detail(cell_id: str) -> SiteDetailResponse:
    """Return full fixture details for a single site cell."""

    try:
        return get_site_detail(cell_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sites/compare", response_model=CompareResponse)
def compare(request: CompareRequest) -> CompareResponse:
    """Compare selected fixture site cells."""

    try:
        return compare_site_cells(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
