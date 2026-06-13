"""Issue 6: build the subset-first JSON artifacts and source metadata rows.

Inputs: a country list (`SE,DE,IE` by default) and the curated
`engine.fixtures.FEATURE_COLLECTION`. Outputs: six processed JSON artifacts
under `data/processed/subset/` plus a manifest, and one upserted row per
artifact in `source_artifacts.db`. The OPF artifact is precomputed; no live
PyPSA solve runs in this path.

Per-source builders live in `_network.py` (PyPSA topology + clustered OPF) and
`_layers.py` (Ember congestion, OSM, connectivity). Shared dataclasses and
helpers live in `_helpers.py`. This module is the orchestrator only.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer

from backend.engine.contracts import SiteFeature
from backend.engine.fixtures import FEATURE_COLLECTION
from backend.pipeline._helpers import (
    ARTIFACT_VERSION,
    SCHEMA_VERSION,
    ArtifactBuild,
    SourceDecision,
    base_payload,
    country_averages,
    decision_for,
    hourly_shape,
)
from backend.pipeline._layers import (
    build_congestion_layers,
    build_connectivity,
    build_osm_features,
)
from backend.pipeline._network import build_precomputed_opf, build_pypsa_network
from backend.pipeline.artifacts import (
    ArtifactSummary,
    display_path,
    upsert_source_artifacts,
    write_json_artifact,
)
from backend.pipeline.constants import DEFAULT_COUNTRIES, DETERMINISTIC_SEED

ROOT_DIR = Path(__file__).resolve().parents[2]

# Re-exported so downstream modules can `from backend.pipeline.subset_ingestion
# import DEFAULT_COUNTRIES, DETERMINISTIC_SEED` without churn.
__all_constants__ = ("DEFAULT_COUNTRIES", "DETERMINISTIC_SEED")


@dataclass(frozen=True)
class IngestionResult:
    countries: tuple[str, ...]
    output_dir: Path
    manifest_path: Path
    metadata_database: Path
    artifacts: list[ArtifactSummary]


# Filter the canonical fixture collection by the default subset country scope.
# Pipelines that need a different country mix should call `_sites_for_countries`
# with their requested scope rather than reach for this tuple directly.
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


app = typer.Typer(add_completion=False, help="Build subset-first ingestion artifacts.")


def parse_countries(raw_countries: str | Sequence[str]) -> tuple[str, ...]:
    """Normalize, dedupe, and validate a comma-separated or sequence input."""

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
    """Build six JSON artifacts + manifest, upsert source rows, return paths."""

    country_codes = parse_countries(countries)
    sites = _sites_for_countries(country_codes)
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_database.parent.mkdir(parents=True, exist_ok=True)

    builds: list[ArtifactBuild] = [
        build_pypsa_network(country_codes, sites, source_decisions, generated_at),
        build_precomputed_opf(country_codes, sites, source_decisions, generated_at),
        _build_hourly_energy(country_codes, sites, source_decisions, generated_at),
        build_congestion_layers(country_codes, sites, source_decisions, generated_at),
        build_osm_features(country_codes, sites, source_decisions, generated_at),
        build_connectivity(country_codes, sites, source_decisions, generated_at),
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


def _sites_for_countries(countries: Sequence[str]) -> list[SiteFeature]:
    """Filter `FEATURE_COLLECTION` by country, raising if no rows match."""

    country_set = set(countries)
    sites = [site for site in FEATURE_COLLECTION if site.country_code in country_set]
    if not sites:
        raise ValueError(f"No fixture cells exist for requested countries: {', '.join(countries)}")
    return sites


def _build_hourly_energy(
    countries: Sequence[str],
    sites: Sequence[SiteFeature],
    source_decisions: Sequence[SourceDecision],
    generated_at: str,
) -> ArtifactBuild:
    """24 hourly rows per country derived from country averages + hour-of-day shape."""

    decision = decision_for(source_decisions, "Ember hourly electricity prices")
    averages_by_country = country_averages(sites)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    records: list[dict[str, object]] = []
    for country in countries:
        averages = averages_by_country[country]
        for hour in range(24):
            shape = hourly_shape(hour)
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
    payload = base_payload(
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
    """CLI entry point: writes artifacts and a manifest, prints a summary."""

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
