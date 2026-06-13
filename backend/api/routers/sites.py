"""Site search, detail, comparison, and map-layer endpoints."""

from typing import Any

from fastapi import APIRouter

from backend.api.routers.errors import key_error_message, not_found
from backend.api.services.site_service import (
    compare_site_cells,
    get_layer,
    get_site_detail,
    search_site_cells,
)
from backend.engine.contracts import (
    ApiErrorResponse,
    CompareRequest,
    CompareResponse,
    LayerResponse,
    SearchRequest,
    SearchResponse,
    SiteDetailResponse,
)

router = APIRouter(tags=["sites"])
NOT_FOUND_RESPONSE: dict[int | str, dict[str, Any]] = {404: {"model": ApiErrorResponse}}


@router.get("/layers/{layer_name}", response_model=LayerResponse, responses=NOT_FOUND_RESPONSE)
def layer(layer_name: str) -> LayerResponse:
    """Return a GeoJSON layer for the requested fixture feature."""

    try:
        return get_layer(layer_name)
    except KeyError as exc:
        raise not_found(key_error_message(exc), code="layer_not_found") from exc


@router.post("/sites/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    """Rank fixture sites for a requested load size."""

    return search_site_cells(request)


@router.get("/sites/{cell_id}", response_model=SiteDetailResponse, responses=NOT_FOUND_RESPONSE)
def site_detail(cell_id: str) -> SiteDetailResponse:
    """Return full fixture details for a single site cell."""

    try:
        return get_site_detail(cell_id)
    except KeyError as exc:
        raise not_found(key_error_message(exc), code="site_not_found") from exc


@router.post("/sites/compare", response_model=CompareResponse, responses=NOT_FOUND_RESPONSE)
def compare(request: CompareRequest) -> CompareResponse:
    """Compare selected fixture site cells."""

    try:
        return compare_site_cells(request)
    except KeyError as exc:
        raise not_found(key_error_message(exc), code="site_not_found") from exc
