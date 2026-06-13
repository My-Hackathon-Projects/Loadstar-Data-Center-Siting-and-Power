"""PyPSA network and OPF artifact builders.

Extracted from `subset_ingestion.py` so the orchestrator stays under 300 lines.
Network topology generation has no public surface; the orchestrator imports
the two builders below and writes the results through `artifacts.write_json_artifact`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict

from backend.engine.contracts import SiteFeature
from backend.pipeline._helpers import (
    ArtifactBuild,
    NetworkLine,
    SourceDecision,
    base_payload,
    decision_for,
    distance_km,
    node_id,
)


def network_lines(sites: Sequence[SiteFeature]) -> list[NetworkLine]:
    """Connect consecutive sites in each country to form a fixture line graph."""

    lines: list[NetworkLine] = []
    for country in sorted({site.country_code for site in sites}):
        country_sites = sorted(
            (site for site in sites if site.country_code == country),
            key=lambda site: site.region_name,
        )
        for left, right in zip(country_sites, country_sites[1:], strict=False):
            congestion = (left.congestion_index + right.congestion_index) / 2
            lines.append(
                NetworkLine(
                    line_id=f"{node_id(left)}__{node_id(right)}",
                    country_code=country,
                    from_cell_id=left.cell_id,
                    to_cell_id=right.cell_id,
                    length_km_proxy=round(
                        distance_km(left.latitude, left.longitude, right.latitude, right.longitude),
                        2,
                    ),
                    capacity_mw_proxy=round((left.headroom_mw + right.headroom_mw) * 0.75, 2),
                    congestion_index_proxy=round(congestion, 3),
                )
            )
    return lines


def build_pypsa_network(
    countries: Sequence[str],
    sites: Sequence[SiteFeature],
    source_decisions: Sequence[SourceDecision],
    generated_at: str,
) -> ArtifactBuild:
    """Fixture PyPSA-Eur network artifact (nodes + lines, no live solve)."""

    decision = decision_for(source_decisions, "Zenodo PyPSA-Eur")
    nodes: list[dict[str, object]] = [
        {
            "node_id": node_id(site),
            "cell_id": site.cell_id,
            "country_code": site.country_code,
            "region_name": site.region_name,
            "latitude": site.latitude,
            "longitude": site.longitude,
            "headroom_mw_proxy": site.headroom_mw,
            "source_method": "fixture_site_features_with_pypsa_pointer_status",
        }
        for site in sites
    ]
    lines = [asdict(line) for line in network_lines(sites)]
    payload = base_payload(
        source="PyPSA-Eur OSM network",
        countries=countries,
        generated_at=generated_at,
        source_status=decision.status,
        fallback=decision.fallback,
        records=[{"nodes": nodes, "lines": lines}],
    )
    return ArtifactBuild(
        name="pypsa_network_subset",
        file_name="pypsa_network_subset.json",
        source="PyPSA-Eur OSM network",
        status="processed_stub",
        source_status=decision.status,
        record_count=len(nodes) + len(lines),
        fallback=decision.fallback,
        notes="Clustered fixture network stub shaped for later PyPSA-Eur CSV replacement.",
        payload=payload,
    )


def build_precomputed_opf(
    countries: Sequence[str],
    sites: Sequence[SiteFeature],
    source_decisions: Sequence[SourceDecision],
    generated_at: str,
) -> ArtifactBuild:
    """Fixture clustered-OPF artifact: line loadings + nodal prices."""

    decision = decision_for(source_decisions, "Zenodo PyPSA-Eur")
    lines = network_lines(sites)
    line_loadings: list[dict[str, object]] = [
        {
            "line_id": line.line_id,
            "from_cell_id": line.from_cell_id,
            "to_cell_id": line.to_cell_id,
            "loading_percent": round(42 + line.congestion_index_proxy * 48, 2),
            "congestion_metric": round(line.congestion_index_proxy, 3),
        }
        for line in lines
    ]
    nodal_prices: list[dict[str, object]] = [
        {
            "node_id": node_id(site),
            "cell_id": site.cell_id,
            "country_code": site.country_code,
            "nodal_price_eur_mwh": round(
                site.mean_price_eur_mwh + site.congestion_index * 18,
                2,
            ),
            "headroom_mw": site.headroom_mw,
        }
        for site in sites
    ]
    payload = base_payload(
        source="PyPSA-Eur clustered OPF",
        countries=countries,
        generated_at=generated_at,
        source_status=decision.status,
        fallback=decision.fallback,
        records=[
            {
                "solver": {
                    "name": "fixture-precomputed",
                    "live_solve": False,
                    "reason": "Issue 6 requires OPF artifacts before the demo path.",
                },
                "line_loadings": line_loadings,
                "nodal_prices": nodal_prices,
            }
        ],
    )
    return ArtifactBuild(
        name="pypsa_clustered_opf",
        file_name="pypsa_clustered_opf.json",
        source="PyPSA-Eur clustered OPF",
        status="precomputed_stub",
        source_status=decision.status,
        record_count=len(line_loadings) + len(nodal_prices),
        fallback=decision.fallback,
        notes="No PyPSA solve runs live; this artifact is generated ahead of demo use.",
        payload=payload,
    )
