"""HTTP-shaped wrappers around site repositories and engine scoring.

No business logic lives here; this layer keeps routers thin and the
engine package free of FastAPI imports.
"""

from backend.api.repositories.site_repository import LAYERABLE_SITE_FIELDS, site_repository
from backend.engine.contracts import (
    CompareRequest,
    CompareResponse,
    LayerFeature,
    LayerFeatureProperties,
    LayerResponse,
    PointGeometry,
    SearchRequest,
    SearchResponse,
    SiteDetailResponse,
)
from backend.engine.scoring import compare_sites, rank_sites, search_sites

from .cache_keys import build_cache_key

ALLOWED_LAYERS = LAYERABLE_SITE_FIELDS | {"composite_score"}


def get_layer(layer_name: str) -> LayerResponse:
    """Return a fixture GeoJSON layer for map rendering."""

    if layer_name not in ALLOWED_LAYERS:
        raise KeyError(f"Unknown layer: {layer_name}")

    sites = site_repository.list_sites()
    composite_scores: dict[str, float] = {}
    if layer_name == "composite_score":
        # Run the same ranking the search endpoint uses, over every cell. We use
        # rank_sites (not search_sites) so the full collection is scored without
        # the request's top_k cap. power_mw=1.0 keeps every cell eligible.
        ranked = rank_sites(SearchRequest(power_mw=1.0), sites)
        composite_scores = {r.site.cell_id: r.composite_score for r in ranked}

    features: list[LayerFeature] = []
    for site in sites:
        if layer_name == "composite_score":
            value = composite_scores.get(site.cell_id, 0.0)
        else:
            value = float(getattr(site, layer_name))
        properties = LayerFeatureProperties(
            **site.model_dump(),
            layer_name=layer_name,
            layer_value=value,
        )
        features.append(
            LayerFeature(
                geometry=PointGeometry(coordinates=(site.longitude, site.latitude)),
                properties=properties,
            )
        )
    return LayerResponse(
        cache_key=build_cache_key("layers", layer_name),
        features=features,
    )


def search_site_cells(request: SearchRequest) -> SearchResponse:
    """Search and rank fixture cells."""

    response = search_sites(request, site_repository.list_sites())
    return response.model_copy(update={"cache_key": build_cache_key("sites.search", request)})


def get_site_detail(cell_id: str) -> SiteDetailResponse:
    """Return detail payload for a selected fixture cell."""

    site = site_repository.get_site(cell_id)
    if site is None:
        raise KeyError(f"Unknown site cell: {cell_id}")
    return SiteDetailResponse(
        cache_key=build_cache_key("sites.detail", cell_id),
        site=site,
    )


def compare_site_cells(request: CompareRequest) -> CompareResponse:
    """Compare fixture cells by ID."""

    response = compare_sites(request, site_repository.list_sites())
    return response.model_copy(update={"cache_key": build_cache_key("sites.compare", request)})
