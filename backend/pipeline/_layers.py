"""Congestion-, OSM-, and connectivity-layer artifact builders.

Extracted from `subset_ingestion.py` so the orchestrator stays under 300 lines.
"""

from __future__ import annotations

from collections.abc import Sequence

from backend.engine.contracts import SiteFeature
from backend.pipeline._helpers import (
    ArtifactBuild,
    SourceDecision,
    base_payload,
    country_averages,
    decision_for,
    osm_record,
)


def build_congestion_layers(
    countries: Sequence[str],
    sites: Sequence[SiteFeature],
    source_decisions: Sequence[SourceDecision],
    generated_at: str,
) -> ArtifactBuild:
    """Country-level summary plus per-hub congestion records."""

    decision = decision_for(source_decisions, "Ember Grids")
    averages = country_averages(sites)
    records: list[dict[str, object]] = [
        {
            "layer_type": "country_summary",
            "country_code": country,
            "mean_congestion_index": round(averages[country]["congestion"], 3),
            "max_congestion_index": round(
                max(site.congestion_index for site in sites if site.country_code == country),
                3,
            ),
            "source_method": "fixture_country_summary_pending_ember_grids",
        }
        for country in countries
    ]
    records.extend(
        {
            "layer_type": "hub_proxy",
            "cell_id": site.cell_id,
            "country_code": site.country_code,
            "hub_name": site.region_name,
            "congestion_index": site.congestion_index,
            "source_method": "fixture_site_congestion_pending_ember_grids",
        }
        for site in sites
    )
    payload = base_payload(
        source="Ember Grids for Data Centres",
        countries=countries,
        generated_at=generated_at,
        source_status=decision.status,
        fallback=decision.fallback,
        records=records,
    )
    return ArtifactBuild(
        name="ember_grids_congestion_layers",
        file_name="ember_grids_congestion_layers.json",
        source="Ember Grids for Data Centres",
        status="fallback_processed",
        source_status=decision.status,
        record_count=len(records),
        fallback=decision.fallback,
        notes="Structured congestion layer ready for official Ember Grids records.",
        payload=payload,
    )


def build_osm_features(
    countries: Sequence[str],
    sites: Sequence[SiteFeature],
    source_decisions: Sequence[SourceDecision],
    generated_at: str,
) -> ArtifactBuild:
    """One row per OSM feature family per cell (substation, water, IXP, ...)."""

    decision = decision_for(source_decisions, "OSM substations")
    records: list[dict[str, object]] = []
    for site in sites:
        records.extend(
            [
                osm_record(site, "substation_proxy", "distance_km", site.dist_hv_substation_km),
                osm_record(
                    site,
                    "known_data_center_proxy",
                    "similarity_score",
                    site.dc_similarity,
                ),
                osm_record(site, "water_proxy", "distance_km", site.water_dist_km),
                osm_record(site, "exclusion_flag_proxy", "excluded", site.exclusion_flag),
                osm_record(site, "ixp_proxy", "distance_km", site.dist_ixp_km),
            ]
        )
    payload = base_payload(
        source="OSM substations, data centers, water, exclusions, and IXPs",
        countries=countries,
        generated_at=generated_at,
        source_status=decision.status,
        fallback=decision.fallback,
        records=records,
    )
    return ArtifactBuild(
        name="osm_site_feature_layers",
        file_name="osm_site_feature_layers.json",
        source="OSM substations, data centers, water, exclusions, and IXPs",
        status="fallback_processed",
        source_status=decision.status,
        record_count=len(records),
        fallback=decision.fallback,
        notes="One structured record per OSM-derived feature family per subset cell.",
        payload=payload,
    )


def build_connectivity(
    countries: Sequence[str],
    sites: Sequence[SiteFeature],
    source_decisions: Sequence[SourceDecision],
    generated_at: str,
) -> ArtifactBuild:
    """Fiber and IXP distance proxy until BBmaps extraction is configured."""

    decision = decision_for(source_decisions, "ITU BBmaps")
    records: list[dict[str, object]] = [
        {
            "cell_id": site.cell_id,
            "country_code": site.country_code,
            "dist_fiber_km": site.dist_fiber_km,
            "dist_ixp_km": site.dist_ixp_km,
            "latency_proxy_ms": site.latency_proxy_ms,
            "fiber_distance_status": "provisional",
            "source_method": "ixp_proxy_fallback",
        }
        for site in sites
    ]
    payload = base_payload(
        source="ITU BBmaps fiber or IXP fallback",
        countries=countries,
        generated_at=generated_at,
        source_status=decision.status,
        fallback=decision.fallback,
        records=records,
    )
    return ArtifactBuild(
        name="connectivity_fiber_or_ixp",
        file_name="connectivity_fiber_or_ixp.json",
        source="ITU BBmaps fiber or IXP fallback",
        status="fallback_processed",
        source_status=decision.status,
        record_count=len(records),
        fallback=decision.fallback,
        notes="Fiber distance remains provisional until BBmaps extraction is configured.",
        payload=payload,
    )
