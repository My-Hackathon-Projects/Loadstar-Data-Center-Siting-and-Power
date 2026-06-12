from api.app.schemas.sites import (
    CompareRequest,
    CompareResponse,
    LayerResponse,
    SearchRequest,
    SearchResponse,
    SiteDetailResponse,
)
from engine.contracts import LayerFeature, LayerFeatureProperties, PointGeometry
from engine.fixtures import FEATURE_COLLECTION, get_site
from engine.scoring import compare_sites, search_sites

ALLOWED_LAYERS = {
    "composite_score",
    "mean_price_eur_mwh",
    "carbon_intensity_g_kwh",
    "congestion_index",
    "headroom_mw",
    "dist_fiber_km",
    "buildable_fraction",
}


def get_layer(layer_name: str) -> LayerResponse:
    """Return a fixture GeoJSON layer for map rendering."""

    if layer_name not in ALLOWED_LAYERS:
        raise KeyError(f"Unknown layer: {layer_name}")

    features: list[LayerFeature] = []
    for site in FEATURE_COLLECTION:
        properties = LayerFeatureProperties(
            **site.model_dump(),
            layer_name=layer_name,
            layer_value=float(getattr(site, layer_name)),
        )
        features.append(
            LayerFeature(
                geometry=PointGeometry(coordinates=(site.longitude, site.latitude)),
                properties=properties,
            )
        )
    return LayerResponse(features=features)


def search_site_cells(request: SearchRequest) -> SearchResponse:
    """Search and rank fixture cells."""

    return search_sites(request)


def get_site_detail(cell_id: str) -> SiteDetailResponse:
    """Return detail payload for a selected fixture cell."""

    site = get_site(cell_id)
    if site is None:
        raise KeyError(f"Unknown site cell: {cell_id}")
    return SiteDetailResponse(site=site)


def compare_site_cells(request: CompareRequest) -> CompareResponse:
    """Compare fixture cells by ID."""

    return compare_sites(request)
