"""Issue 8: build per-cell ranking features from the subset artifacts.

Reads `hourly_carbon_subset.json`, `pypsa_clustered_opf.json`, the Ember
congestion layers, the AlphaEarth land artifact, and the siting-model
artifact; produces `site_features_subset.json` with normalized score
inputs (5/95 percentile clip, not min-max), the blended congestion index,
and explicit missing-data flags for any fallback source.

Artifact loading lives in `_feature_context.py`; record assembly +
normalization lives in `_feature_blending.py`. This module is the
orchestrator only.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from backend.engine.contracts import SiteFeature
from backend.pipeline._feature_blending import (
    CLIP_LOWER_PERCENTILE,
    CLIP_UPPER_PERCENTILE,
    CONGESTION_BLEND_WEIGHTS,
    FEATURE_DIRECTIONS,
    NORMALIZATION_METHOD,
    final_feature_record,
    normalized_score_inputs,
    raw_feature_record,
)
from backend.pipeline._feature_context import load_context
from backend.pipeline.artifacts import (
    ArtifactSummary,
    display_path,
    upsert_source_artifacts,
    write_json_artifact,
)
from backend.pipeline.constants import DETERMINISTIC_SEED
from backend.pipeline.subset_ingestion import (
    DEFAULT_COUNTRIES,
    FIXTURE_SITES,
    parse_countries,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "loadstar.site_features.v1"
ARTIFACT_VERSION = "site-features-v1"

app = typer.Typer(add_completion=False, help="Build subset per-cell ranking features.")


@dataclass(frozen=True)
class FeatureEngineeringResult:
    countries: tuple[str, ...]
    output_path: Path
    metadata_database: Path
    record_count: int
    checksum_sha256: str


def run_feature_engineering(
    countries: str | Sequence[str] = DEFAULT_COUNTRIES,
    input_dir: Path = ROOT_DIR / "data" / "processed" / "subset",
    output_dir: Path = ROOT_DIR / "data" / "processed" / "subset",
    metadata_database: Path = ROOT_DIR / "data" / "processed" / "source_artifacts.db",
) -> FeatureEngineeringResult:
    """Compose the upstream artifacts into `site_features_subset.json`."""

    country_codes = parse_countries(countries)
    sites = _sites_for_countries(country_codes)
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    context = load_context(input_dir)
    raw_records = [raw_feature_record(site, context) for site in sites]
    normalized = normalized_score_inputs(raw_records)
    records = [
        final_feature_record(raw_record, normalized[index], context, ARTIFACT_VERSION)
        for index, raw_record in enumerate(raw_records)
    ]

    output_path = output_dir / "site_features_subset.json"
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_version": ARTIFACT_VERSION,
        "deterministic_seed": DETERMINISTIC_SEED,
        "generated_at": generated_at,
        "countries": list(country_codes),
        "normalization": {
            "method": NORMALIZATION_METHOD,
            "lower_percentile": CLIP_LOWER_PERCENTILE,
            "upper_percentile": CLIP_UPPER_PERCENTILE,
            "directions": FEATURE_DIRECTIONS,
        },
        "congestion_blend_weights": CONGESTION_BLEND_WEIGHTS,
        "source_context": context.summary,
        "records": records,
    }
    checksum = write_json_artifact(output_path, payload)
    summary = ArtifactSummary(
        name="site_features_subset",
        source="Loadstar subset feature engineering",
        status="processed",
        source_status="generated",
        path=display_path(output_path, ROOT_DIR),
        checksum_sha256=checksum,
        artifact_version=ARTIFACT_VERSION,
        record_count=len(records),
        fallback=None,
        notes="Per-cell ranking features with normalized score inputs and missing-data flags.",
    )
    upsert_source_artifacts(
        metadata_database=metadata_database,
        countries=country_codes,
        generated_at=generated_at,
        artifacts=[summary],
    )
    return FeatureEngineeringResult(
        countries=country_codes,
        output_path=output_path,
        metadata_database=metadata_database,
        record_count=len(records),
        checksum_sha256=checksum,
    )


def _sites_for_countries(countries: Sequence[str]) -> list[SiteFeature]:
    """Filter the curated subset by requested country, raising on empty result."""

    country_set = set(countries)
    sites = [site for site in FIXTURE_SITES if site.country_code in country_set]
    if not sites:
        raise ValueError(f"No fixture cells exist for requested countries: {', '.join(countries)}")
    return sites


@app.callback(invoke_without_command=True)
def main(
    countries: Annotated[
        str,
        typer.Option(
            "--countries",
            help="Comma-separated ISO-3166 alpha-2 countries to process.",
        ),
    ] = ",".join(DEFAULT_COUNTRIES),
    input_dir: Annotated[
        Path,
        typer.Option("--input-dir", help="Directory containing upstream subset artifacts."),
    ] = ROOT_DIR / "data" / "processed" / "subset",
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", help="Directory for the site features artifact."),
    ] = ROOT_DIR / "data" / "processed" / "subset",
    metadata_database: Annotated[
        Path,
        typer.Option(
            "--metadata-database",
            help="SQLite database where source_artifacts rows are upserted.",
        ),
    ] = ROOT_DIR / "data" / "processed" / "source_artifacts.db",
) -> None:
    """CLI entry point: build the feature artifact and update source metadata."""

    result = run_feature_engineering(
        countries=countries,
        input_dir=input_dir,
        output_dir=output_dir,
        metadata_database=metadata_database,
    )
    typer.echo(f"Wrote site features artifact: {result.output_path}")
    typer.echo(f"Updated source_artifacts metadata: {result.metadata_database}")
    typer.echo(f"- records={result.record_count}; checksum={result.checksum_sha256[:12]}")


if __name__ == "__main__":
    app()
