"""Fixture-backed site repository.

This keeps API services independent of the current storage implementation. The
live PostGIS switch can replace this adapter without changing routers or engine
scoring interfaces.
"""

from collections.abc import Sequence

from backend.engine.contracts import SiteFeature
from backend.engine.fixtures import FEATURE_COLLECTION

LAYERABLE_SITE_FIELDS = frozenset(
    {
        "mean_price_eur_mwh",
        "carbon_intensity_g_kwh",
        "congestion_index",
        "headroom_mw",
        "dist_fiber_km",
        "buildable_fraction",
    }
)


class FixtureSiteRepository:
    """Read-only site repository over deterministic fixture data."""

    def list_sites(self) -> Sequence[SiteFeature]:
        return FEATURE_COLLECTION

    def get_site(self, cell_id: str) -> SiteFeature | None:
        return next((site for site in FEATURE_COLLECTION if site.cell_id == cell_id), None)


site_repository = FixtureSiteRepository()
