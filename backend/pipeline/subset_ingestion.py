"""Issue 6: build the subset-first JSON artifacts and source metadata rows.

Inputs: a country list (`SE,DE,IE` by default) and the curated
`engine.fixtures.FEATURE_COLLECTION`. Outputs: six processed JSON
artifacts under `data/processed/subset/` plus a manifest, and one
upserted row per artifact in `source_artifacts.db`. The OPF artifact
is precomputed; no live PyPSA solve runs in this path.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Annotated

import typer

from backend.engine.contracts import SiteFeature
from backend.engine.fixtures import FEATURE_COLLECTION
from backend.pipeline.artifacts import (
    ArtifactSummary,
    display_path,
    upsert_source_artifacts,
    write_json_artifact,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_COUNTRIES = ("SE", "DE", "IE")
SCHEMA_VERSION = "loadstar.subset_ingestion.v1"
ARTIFACT_VERSION = "subset-fixture-proxy-v1"
DETERMINISTIC_SEED = 20260612

app = typer.Typer(add_completion=False, help="Build subset-first ingestion artifacts.")


@dataclass(frozen=True)
class SourceDecision:
    source: str
    status: str
    fallback: str | None


@dataclass(frozen=True)
class NetworkLine:
    line_id: str
    country_code: str
    from_cell_id: str
    to_cell_id: str
    length_km_proxy: float
    capacity_mw_proxy: float
    congestion_index_proxy: float


@dataclass(frozen=True)
class ArtifactBuild:
    name: str
    file_name: str
    source: str
    status: str
    source_status: str
    record_count: int
    fallback: str | None
    notes: str
    payload: dict[str, object]


@dataclass(frozen=True)
class IngestionResult:
    countries: tuple[str, ...]
    output_dir: Path
    manifest_path: Path
    metadata_database: Path
    artifacts: list[ArtifactSummary]


FIXTURE_SITES: tuple[SiteFeature, ...] = tuple(
    site for site in FEATURE_COLLECTION if site.country_code in set(DEFAULT_COUNTRIES)
)


DEFAULT_SOURCE_DECISIONS: tuple[SourceDecision, ...] = (
    SourceDecision(
        source="Zenodo PyPSA-Eur record 18619025",
        status="stubbed",
        fallback="Use clustered fixture network until PyPSA-Eur CSV parsing is wired.",
    ),
    SourceDecision(
        source="Ember hourly electricity prices and carbon",
        status="fallback",
        fallback="Use fixture hourly price/carbon shapes until an Ember endpoint is configured.",
    ),
    SourceDecision(
        source="Ember Grids for Data Centres",
        status="fallback",
        fallback="Use structured fixture congestion layers until official records are ingested.",
    ),
    SourceDecision(
        source="OSM substations, data centers, water, exclusions, and IXPs",
        status="fallback",
        fallback="Use fixture distance and exclusion proxies until OSM extracts are wired.",
    ),
    SourceDecision(
        source="ITU BBmaps fiber data",
        status="fallback",
        fallback="Use IXP distance proxy and mark fiber distances provisional.",
    ),
)


def parse_countries(raw_countries: str | Sequence[str]) -> tuple[str, ...]:
    tokens = raw_countries.split(",") if isinstance(raw_countries, str) else list(raw_countries)
    countries: list[str] = []
    for token in tokens:
        code = token.strip().upper()
        if not code:
            continue
        if len(code) != 2 or not code.isalpha():
            raise ValueError(f"Invalid country code: {token!r}")
        if code not in countries:
            countries.append(code)
    if not countries:
        raise ValueError("At least one country code is required.")
    return tuple(countries)


def run_subset_ingestion(
    countries: str | Sequence[str] = DEFAULT_COUNTRIES,
    output_dir: Path = ROOT_DIR / "data" / "processed" / "subset",
    metadata_database: Path = ROOT_DIR / "data" / "processed" / "source_artifacts.db",
    source_decisions: Sequence[SourceDecision] = DEFAULT_SOURCE_DECISIONS,
) -> IngestionResult:
    country_codes = parse_countries(countries)
    sites = _sites_for_countries(country_codes)
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_database.parent.mkdir(parents=True, exist_ok=True)

    builds = [
        _build_pypsa_network(country_codes, sites, source_decisions, generated_at),
        _build_precomputed_opf(country_codes, sites, source_decisions, generated_at),
        _build_hourly_energy(country_codes, sites, source_decisions, generated_at),
        _build_congestion_layers(country_codes, sites, source_decisions, generated_at),
        _build_osm_features(country_codes, sites, source_decisions, generated_at),
        _build_connectivity(country_codes, sites, source_decisions, generated_at),
    ]

    summaries: list[ArtifactSummary] = []
    for build in builds:
        path = output_dir / build.file_name
        checksum = write_json_artifact(path, build.payload)
        summaries.append(
            ArtifactSummary(
                name=build.name,
                source=build.source,
                status=build.status,
                source_status=build.source_status,
                path=display_path(path, ROOT_DIR),
                checksum_sha256=checksum,
                artifact_version=ARTIFACT_VERSION,
                record_count=build.record_count,
                fallback=build.fallback,
                notes=build.notes,
            )
        )

    manifest_path = output_dir / "manifest.json"
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_version": ARTIFACT_VERSION,
        "deterministic_seed": DETERMINISTIC_SEED,
        "generated_at": generated_at,
        "countries": list(country_codes),
        "artifacts": [asdict(summary) for summary in summaries],
    }
    manifest_checksum = write_json_artifact(manifest_path, manifest)
    manifest_summary = ArtifactSummary(
        name="subset_ingestion_manifest",
        source="Loadstar subset ingestion",
        status="processed",
        source_status="generated",
        path=display_path(manifest_path, ROOT_DIR),
        checksum_sha256=manifest_checksum,
        artifact_version=ARTIFACT_VERSION,
        record_count=len(summaries),
        fallback=None,
        notes="Manifest for all generated subset ingestion artifacts.",
    )

    upsert_source_artifacts(
        metadata_database=metadata_database,
        countries=country_codes,
        generated_at=generated_at,
        artifacts=[*summaries, manifest_summary],
    )

    return IngestionResult(
        countries=country_codes,
        output_dir=output_dir,
        manifest_path=manifest_path,
        metadata_database=metadata_database,
        artifacts=summaries,
    )


def _build_pypsa_network(
    countries: Sequence[str],
    sites: Sequence[SiteFeature],
    source_decisions: Sequence[SourceDecision],
    generated_at: str,
) -> ArtifactBuild:
    decision = _decision_for(source_decisions, "Zenodo PyPSA-Eur")
    nodes: list[dict[str, object]] = [
        {
            "node_id": _node_id(site),
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
    lines = [asdict(line) for line in _network_lines(sites)]
    payload = _base_payload(
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


def _build_precomputed_opf(
    countries: Sequence[str],
    sites: Sequence[SiteFeature],
    source_decisions: Sequence[SourceDecision],
    generated_at: str,
) -> ArtifactBuild:
    decision = _decision_for(source_decisions, "Zenodo PyPSA-Eur")
    lines = _network_lines(sites)
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
            "node_id": _node_id(site),
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
    payload = _base_payload(
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


def _build_hourly_energy(
    countries: Sequence[str],
    sites: Sequence[SiteFeature],
    source_decisions: Sequence[SourceDecision],
    generated_at: str,
) -> ArtifactBuild:
    decision = _decision_for(source_decisions, "Ember hourly electricity prices")
    country_averages = _country_averages(sites)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    records: list[dict[str, object]] = []
    for country in countries:
        averages = country_averages[country]
        for hour in range(24):
            shape = _hourly_shape(hour)
            records.append(
                {
                    "zone_id": country,
                    "timestamp_utc": (start + timedelta(hours=hour)).isoformat(),
                    "price_eur_mwh": round(averages["price"] * shape["price"], 2),
                    "carbon_g_kwh": round(averages["carbon"] * shape["carbon"], 2),
                    "solar_cf": round(averages["solar_cf"] * shape["solar"], 4),
                    "wind_cf": round(averages["wind_cf"] * shape["wind"], 4),
                    "source_method": "fixture_hourly_shape_from_site_features",
                }
            )
    payload = _base_payload(
        source="Ember hourly prices and carbon",
        countries=countries,
        generated_at=generated_at,
        source_status=decision.status,
        fallback=decision.fallback,
        records=records,
    )
    return ArtifactBuild(
        name="hourly_energy_subset",
        file_name="hourly_energy_subset.json",
        source="Ember hourly prices and carbon",
        status="fallback_processed",
        source_status=decision.status,
        record_count=len(records),
        fallback=decision.fallback,
        notes="Matches hourly_energy columns for later real Ember or ENTSO-E replacement.",
        payload=payload,
    )


def _build_congestion_layers(
    countries: Sequence[str],
    sites: Sequence[SiteFeature],
    source_decisions: Sequence[SourceDecision],
    generated_at: str,
) -> ArtifactBuild:
    decision = _decision_for(source_decisions, "Ember Grids")
    country_averages = _country_averages(sites)
    records: list[dict[str, object]] = [
        {
            "layer_type": "country_summary",
            "country_code": country,
            "mean_congestion_index": round(country_averages[country]["congestion"], 3),
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
    payload = _base_payload(
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


def _build_osm_features(
    countries: Sequence[str],
    sites: Sequence[SiteFeature],
    source_decisions: Sequence[SourceDecision],
    generated_at: str,
) -> ArtifactBuild:
    decision = _decision_for(source_decisions, "OSM substations")
    records: list[dict[str, object]] = []
    for site in sites:
        records.extend(
            [
                _osm_record(site, "substation_proxy", "distance_km", site.dist_hv_substation_km),
                _osm_record(
                    site,
                    "known_data_center_proxy",
                    "similarity_score",
                    site.dc_similarity,
                ),
                _osm_record(site, "water_proxy", "distance_km", site.water_dist_km),
                _osm_record(site, "exclusion_flag_proxy", "excluded", site.exclusion_flag),
                _osm_record(site, "ixp_proxy", "distance_km", site.dist_ixp_km),
            ]
        )
    payload = _base_payload(
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


def _build_connectivity(
    countries: Sequence[str],
    sites: Sequence[SiteFeature],
    source_decisions: Sequence[SourceDecision],
    generated_at: str,
) -> ArtifactBuild:
    decision = _decision_for(source_decisions, "ITU BBmaps")
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
    payload = _base_payload(
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


def _base_payload(
    *,
    source: str,
    countries: Sequence[str],
    generated_at: str,
    source_status: str,
    fallback: str | None,
    records: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_version": ARTIFACT_VERSION,
        "deterministic_seed": DETERMINISTIC_SEED,
        "generated_at": generated_at,
        "source": source,
        "source_status": source_status,
        "countries": list(countries),
        "fallback": fallback,
        "records": records,
    }


def _sites_for_countries(countries: Sequence[str]) -> list[SiteFeature]:
    country_set = set(countries)
    sites = [site for site in FIXTURE_SITES if site.country_code in country_set]
    if not sites:
        raise ValueError(f"No fixture cells exist for requested countries: {', '.join(countries)}")
    return sites


def _network_lines(sites: Sequence[SiteFeature]) -> list[NetworkLine]:
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
                    line_id=f"{_node_id(left)}__{_node_id(right)}",
                    country_code=country,
                    from_cell_id=left.cell_id,
                    to_cell_id=right.cell_id,
                    length_km_proxy=round(
                        _distance_km(
                            left.latitude,
                            left.longitude,
                            right.latitude,
                            right.longitude,
                        ),
                        2,
                    ),
                    capacity_mw_proxy=round((left.headroom_mw + right.headroom_mw) * 0.75, 2),
                    congestion_index_proxy=round(congestion, 3),
                )
            )
    return lines


def _country_averages(sites: Sequence[SiteFeature]) -> dict[str, dict[str, float]]:
    averages: dict[str, dict[str, float]] = {}
    for country in sorted({site.country_code for site in sites}):
        country_sites = [site for site in sites if site.country_code == country]
        count = len(country_sites)
        averages[country] = {
            "price": sum(site.mean_price_eur_mwh for site in country_sites) / count,
            "carbon": sum(site.carbon_intensity_g_kwh for site in country_sites) / count,
            "solar_cf": sum(site.solar_cf for site in country_sites) / count,
            "wind_cf": sum(site.wind_cf for site in country_sites) / count,
            "congestion": sum(site.congestion_index for site in country_sites) / count,
        }
    return averages


def _hourly_shape(hour: int) -> dict[str, float]:
    daytime = 8 <= hour <= 18
    evening_peak = 17 <= hour <= 21
    night = hour <= 5 or hour >= 23
    return {
        "price": 1.18 if evening_peak else 0.88 if night else 1.0,
        "carbon": 1.08 if evening_peak else 0.94 if night else 1.0,
        "solar": 1.0 if daytime else 0.0,
        "wind": 1.08 if night else 0.96 if daytime else 1.0,
    }


def _osm_record(
    site: SiteFeature,
    asset_type: str,
    value_key: str,
    value: float | bool,
) -> dict[str, object]:
    return {
        "asset_type": asset_type,
        "cell_id": site.cell_id,
        "country_code": site.country_code,
        value_key: value,
        "source_method": f"fixture_{asset_type}",
    }


def _decision_for(decisions: Sequence[SourceDecision], source_prefix: str) -> SourceDecision:
    return next(decision for decision in decisions if decision.source.startswith(source_prefix))


def _node_id(site: SiteFeature) -> str:
    return f"{site.country_code}-{site.cell_id[-6:]}"


def _distance_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    radius_km = 6371.0
    delta_lat = radians(lat_b - lat_a)
    delta_lon = radians(lon_b - lon_a)
    start_lat = radians(lat_a)
    end_lat = radians(lat_b)
    haversine = sin(delta_lat / 2) ** 2 + cos(start_lat) * cos(end_lat) * sin(delta_lon / 2) ** 2
    return 2 * radius_km * asin(sqrt(haversine))


@app.callback(invoke_without_command=True)
def main(
    countries: Annotated[
        str,
        typer.Option(
            "--countries",
            help="Comma-separated ISO-3166 alpha-2 countries to process.",
        ),
    ] = ",".join(DEFAULT_COUNTRIES),
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", help="Directory for processed subset artifacts."),
    ] = ROOT_DIR / "data" / "processed" / "subset",
    metadata_database: Annotated[
        Path,
        typer.Option(
            "--metadata-database",
            help="SQLite database where source_artifacts rows are upserted.",
        ),
    ] = ROOT_DIR / "data" / "processed" / "source_artifacts.db",
) -> None:
    result = run_subset_ingestion(
        countries=countries,
        output_dir=output_dir,
        metadata_database=metadata_database,
    )
    typer.echo(f"Wrote subset ingestion manifest: {result.manifest_path}")
    typer.echo(f"Updated source_artifacts metadata: {result.metadata_database}")
    for artifact in result.artifacts:
        typer.echo(
            f"- {artifact.name}: {artifact.status}; records={artifact.record_count}; "
            f"checksum={artifact.checksum_sha256[:12]}; path={artifact.path}"
        )


if __name__ == "__main__":
    app()
