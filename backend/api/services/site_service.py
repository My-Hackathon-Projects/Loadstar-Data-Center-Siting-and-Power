"""HTTP-shaped wrappers around engine.scoring and engine.fixtures.

No business logic lives here; this layer keeps routers thin and the
engine package free of FastAPI imports.
"""

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
from backend.engine.fixtures import FEATURE_COLLECTION, get_site
from backend.engine.scoring import compare_sites, search_sites

# Raw `SiteFeature` columns we expose as a map layer. `composite_score` is
# handled separately because it is computed, not a column.
_RAW_LAYER_FIELDS = {
    "mean_price_eur_mwh",
    "carbon_intensity_g_kwh",
    "congestion_index",
    "headroom_mw",
    "dist_fiber_km",
    "buildable_fraction",
}
ALLOWED_LAYERS = _RAW_LAYER_FIELDS | {"composite_score"}


def get_layer(layer_name: str) -> LayerResponse:
    """Return a fixture GeoJSON layer for map rendering."""

    if layer_name not in ALLOWED_LAYERS:
        raise KeyError(f"Unknown layer: {layer_name}")

    composite_scores: dict[str, float] = {}
    if layer_name == "composite_score":
        # Run the same ranking the search endpoint uses, then index by cell_id.
        ranked = search_sites(
            SearchRequest(power_mw=1.0, top_k=len(FEATURE_COLLECTION))
        )
        composite_scores = {r.site.cell_id: r.composite_score for r in ranked.results}

    features: list[LayerFeature] = []
    for site in FEATURE_COLLECTION:
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
