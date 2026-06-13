"""Build optimizer-ready hourly price rows from the local Ember CSV ingest.

Preferred method: read the per-country profile + hourly shape that
`ember/ingest.py` writes into `ember/dataset/ember_prices.db` (real 2025
Ember wholesale day-ahead prices, country-level).
Active fallback: broadcast the curated reference price from
`backend/engine/data/europe_sites.json` so the demo never breaks when the
Ember DB is missing or stale. Both paths produce the same output schema —
downstream consumers (the feature blender) only need to know that
`hourly_price_subset.json` exists.

Read-only against `ember/dataset/ember_prices.db`. We never write back to
that DB; the side-channel SQLite is purely an upstream input here.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean
from typing import Annotated, Literal

import typer

from backend.engine.contracts import SiteFeature
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
SCHEMA_VERSION = "loadstar.hourly_price.v1"
ARTIFACT_VERSION = "hourly-price-v1"
DEFAULT_EMBER_DB = ROOT_DIR / "ember" / "dataset" / "ember_prices.db"

PreferredMethod = Literal["ember_csv_local_db"]
FallbackMethod = Literal["fixture_static_price"]
ActiveMethod = PreferredMethod | FallbackMethod

app = typer.Typer(add_completion=False, help="Build optimizer-ready hourly price artifacts.")


@dataclass(frozen=True)
class HourlyPriceResult:
    countries: tuple[str, ...]
    output_path: Path
    metadata_database: Path
    active_method: ActiveMethod
    source_version: str
    record_count: int
    checksum_sha256: str


@dataclass(frozen=True)
class _CountryPriceProfile:
    """One row of the per-country profile written into the artifact."""

    zone_id: str
    sample_year: int | None
    mean_price_eur_mwh: float
    price_volatility: float
    sample_hours: int
    hour_shape: list[float]  # 24 multipliers around 1.0; index 0 is 00:00 UTC
    hour_mean_price_eur_mwh: list[float]  # 24 absolute EUR/MWh
    source_method: ActiveMethod


def run_hourly_price_ingestion(
    countries: str | Sequence[str] = DEFAULT_COUNTRIES,
    output_dir: Path = ROOT_DIR / "data" / "processed" / "subset",
    metadata_database: Path = ROOT_DIR / "data" / "processed" / "source_artifacts.db",
    ember_db_path: Path = DEFAULT_EMBER_DB,
    method: str = "auto",
) -> HourlyPriceResult:
    """Read Ember when present, fall back to fixture price otherwise."""

    country_codes = parse_countries(countries)
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    sites = _sites_for_countries(country_codes)
    selected_method = _select_method(method, ember_db_path)

    profiles: list[_CountryPriceProfile]
    if selected_method == "ember_csv_local_db":
        profiles = _profiles_from_ember(country_codes, ember_db_path)
        source_version = f"ember-csv-local-db:{ember_db_path.name}"
        status = "processed"
        source_status = "preferred"
        fallback = None
    else:
        profiles = _profiles_from_fixture(country_codes, sites)
        source_version = "fixture-static-price-v1"
        status = "fallback_processed"
        source_status = "fallback"
        fallback = (
            "Ember price DB unavailable; broadcast curated mean price from europe_sites.json."
        )

    output_path = output_dir / "hourly_price_subset.json"
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_version": ARTIFACT_VERSION,
        "deterministic_seed": DETERMINISTIC_SEED,
        "generated_at": generated_at,
        "countries": list(country_codes),
        "preferred_method": "ember_csv_local_db",
        "fallback_method": "fixture_static_price",
        "active_method": selected_method,
        "source_version": source_version,
        "records": [_profile_to_record(profile) for profile in profiles],
    }
    checksum = write_json_artifact(output_path, payload)
    summary = ArtifactSummary(
        name="hourly_price_subset",
        source="Ember CSV (local SQLite) / curated reference price fallback",
        status=status,
        source_status=source_status,
        path=display_path(output_path, ROOT_DIR),
        checksum_sha256=checksum,
        artifact_version=ARTIFACT_VERSION,
        record_count=len(profiles),
        fallback=fallback,
        notes=(
            "Per-country price profile + 24-hour shape that the feature blender "
            "overlays onto matching cells' mean_price_eur_mwh and price_volatility."
        ),
    )
    upsert_source_artifacts(
        metadata_database=metadata_database,
        countries=country_codes,
        generated_at=generated_at,
        artifacts=[summary],
    )
    return HourlyPriceResult(
        countries=country_codes,
        output_path=output_path,
        metadata_database=metadata_database,
        active_method=selected_method,
        source_version=source_version,
        record_count=len(profiles),
        checksum_sha256=checksum,
    )


def _select_method(method: str, ember_db_path: Path) -> ActiveMethod:
    """Pick the active method.

    `--method ember` requires the DB to exist; `--method auto` (default)
    prefers Ember when the DB is present and falls through to the fixture
    broadcast otherwise. `--method fixture` forces the fallback even if the
    DB is on disk (useful for tests).
    """

    normalized = method.strip().lower()
    if normalized not in {"auto", "ember", "fixture"}:
        raise ValueError("method must be one of: auto, ember, fixture")
    if normalized == "ember":
        if not ember_db_path.exists():
            raise ValueError(
                f"--method ember was requested but {ember_db_path} does not exist. "
                "Run `python3 ember/ingest.py` first."
            )
        return "ember_csv_local_db"
    if normalized == "auto" and ember_db_path.exists():
        return "ember_csv_local_db"
    return "fixture_static_price"


def _profiles_from_ember(
    countries: Sequence[str],
    ember_db_path: Path,
) -> list[_CountryPriceProfile]:
    """Read per-country profile rows + 24-hour shape from the Ember SQLite DB.

    The DB is the output of `ember/ingest.py`. We only consume the latest
    `sample_year` per zone — running Ember ingest for multiple years
    just adds rows, never replaces them, so the latest year is the one we
    want.
    """

    profiles: list[_CountryPriceProfile] = []
    with sqlite3.connect(f"file:{ember_db_path}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        for zone_id in countries:
            profile_row = connection.execute(
                """
                SELECT zone_id, sample_year, mean_price_eur_mwh,
                       price_volatility, sample_hours
                  FROM ember_price_profile
                  WHERE zone_id = ?
                  ORDER BY sample_year DESC
                  LIMIT 1
                """,
                (zone_id,),
            ).fetchone()
            if profile_row is None:
                raise ValueError(
                    f"Ember DB at {ember_db_path} has no profile for {zone_id}. "
                    f"Run `python3 ember/ingest.py --countries {','.join(countries)}` first."
                )
            sample_year = int(profile_row["sample_year"])
            shape_rows = connection.execute(
                """
                SELECT hour, shape_multiplier, hour_mean_price_eur_mwh
                  FROM ember_price_hourly_shape
                  WHERE zone_id = ? AND sample_year = ?
                  ORDER BY hour
                """,
                (zone_id, sample_year),
            ).fetchall()
            if len(shape_rows) != 24:
                raise ValueError(
                    f"Ember DB at {ember_db_path} has {len(shape_rows)} shape rows for "
                    f"{zone_id} {sample_year}, expected 24."
                )
            profiles.append(
                _CountryPriceProfile(
                    zone_id=zone_id,
                    sample_year=sample_year,
                    mean_price_eur_mwh=float(profile_row["mean_price_eur_mwh"]),
                    price_volatility=float(profile_row["price_volatility"]),
                    sample_hours=int(profile_row["sample_hours"]),
                    hour_shape=[float(row["shape_multiplier"]) for row in shape_rows],
                    hour_mean_price_eur_mwh=[
                        float(row["hour_mean_price_eur_mwh"]) for row in shape_rows
                    ],
                    source_method="ember_csv_local_db",
                )
            )
    return profiles


def _profiles_from_fixture(
    countries: Sequence[str],
    sites: Sequence[SiteFeature],
) -> list[_CountryPriceProfile]:
    """Average curated cell prices per country to produce a flat fallback profile.

    The fallback is intentionally flat (shape multiplier = 1.0 every hour).
    A synthetic shape would be misleading; the whole point of the Ember
    overlay is to replace fixture flatness with real shape, so when Ember
    is absent we just say "no shape information available" by emitting a
    constant.
    """

    profiles: list[_CountryPriceProfile] = []
    for country in countries:
        country_sites = [site for site in sites if site.country_code == country]
        if not country_sites:
            raise ValueError(f"No fixture sites for {country}; cannot build fallback profile.")
        mean_price = round(
            fmean(site.mean_price_eur_mwh for site in country_sites), 2
        )
        volatility = round(
            fmean(site.price_volatility for site in country_sites), 2
        )
        profiles.append(
            _CountryPriceProfile(
                zone_id=country,
                sample_year=None,
                mean_price_eur_mwh=mean_price,
                price_volatility=volatility,
                sample_hours=0,
                hour_shape=[1.0] * 24,
                hour_mean_price_eur_mwh=[mean_price] * 24,
                source_method="fixture_static_price",
            )
        )
    return profiles


def _profile_to_record(profile: _CountryPriceProfile) -> dict[str, object]:
    return {
        "zone_id": profile.zone_id,
        "sample_year": profile.sample_year,
        "mean_price_eur_mwh": round(profile.mean_price_eur_mwh, 2),
        "price_volatility": round(profile.price_volatility, 2),
        "sample_hours": profile.sample_hours,
        "hour_shape": [round(value, 4) for value in profile.hour_shape],
        "hour_mean_price_eur_mwh": [
            round(value, 2) for value in profile.hour_mean_price_eur_mwh
        ],
        "source_method": profile.source_method,
    }


def _sites_for_countries(countries: Sequence[str]) -> list[SiteFeature]:
    country_set = set(countries)
    sites = [site for site in FIXTURE_SITES if site.country_code in country_set]
    if not sites:
        raise ValueError(f"No fixture cells exist for requested countries: {', '.join(countries)}")
    return sites


@app.callback(invoke_without_command=True)
def main(
    countries: Annotated[
        str,
        typer.Option("--countries", help="Comma-separated ISO-3166 alpha-2 countries."),
    ] = ",".join(DEFAULT_COUNTRIES),
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", help="Directory for processed subset artifacts."),
    ] = ROOT_DIR / "data" / "processed" / "subset",
    metadata_database: Annotated[
        Path,
        typer.Option("--metadata-database", help="SQLite source_artifacts metadata database."),
    ] = ROOT_DIR / "data" / "processed" / "source_artifacts.db",
    ember_db_path: Annotated[
        Path,
        typer.Option(
            "--ember-db",
            help="Path to ember_prices.db produced by `python3 ember/ingest.py`.",
        ),
    ] = DEFAULT_EMBER_DB,
    method: Annotated[
        str,
        typer.Option("--method", help="auto, ember, or fixture."),
    ] = "auto",
) -> None:
    """CLI entry point: build the per-country price artifact."""

    result = run_hourly_price_ingestion(
        countries=countries,
        output_dir=output_dir,
        metadata_database=metadata_database,
        ember_db_path=ember_db_path,
        method=method,
    )
    typer.echo(f"Wrote hourly price artifact: {result.output_path}")
    typer.echo(f"Updated source_artifacts metadata: {result.metadata_database}")
    typer.echo(
        f"- active_method={result.active_method}; records={result.record_count}; "
        f"checksum={result.checksum_sha256[:12]}"
    )


if __name__ == "__main__":
    app()
