"""Issue 7: build optimizer-ready hourly carbon-intensity rows.

Preferred method: ENTSO-E generation mix x technology emission factors.
Active fallback: Ember-style monthly carbon broadcast across each hour
in the month. The chosen method and source version are recorded in the
artifact payload so downstream consumers can detect fallback runs.
"""

from __future__ import annotations

import calendar
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal, cast

import typer

from backend.engine.contracts import SiteFeature
from backend.pipeline.artifacts import (
    ArtifactSummary,
    display_path,
    upsert_source_artifacts,
    write_json_artifact,
)
from backend.pipeline.subset_ingestion import (
    DEFAULT_COUNTRIES,
    FIXTURE_SITES,
    parse_countries,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "loadstar.hourly_carbon.v1"
ARTIFACT_VERSION = "hourly-carbon-v1"
DETERMINISTIC_SEED = 20260612
DEFAULT_YEAR = 2026

PreferredMethod = Literal["entsoe_hourly_generation_mix"]
FallbackMethod = Literal["ember_monthly_repeat"]
ActiveMethod = PreferredMethod | FallbackMethod

TECH_EMISSION_FACTORS_G_KWH: dict[str, float] = {
    "biomass": 230.0,
    "coal": 820.0,
    "gas": 490.0,
    "geothermal": 38.0,
    "hydro": 24.0,
    "nuclear": 12.0,
    "oil": 650.0,
    "other": 500.0,
    "other_fossil": 700.0,
    "other_renewable": 40.0,
    "solar": 45.0,
    "wind": 11.0,
}

TECH_ALIASES: dict[str, str] = {
    "fossil_gas": "gas",
    "hard_coal": "coal",
    "lignite": "coal",
    "natural_gas": "gas",
    "offshore_wind": "wind",
    "onshore_wind": "wind",
    "wind_offshore": "wind",
    "wind_onshore": "wind",
}

MONTHLY_CARBON_FACTORS: dict[int, float] = {
    1: 1.06,
    2: 1.04,
    3: 1.00,
    4: 0.95,
    5: 0.91,
    6: 0.89,
    7: 0.92,
    8: 0.94,
    9: 0.97,
    10: 1.00,
    11: 1.03,
    12: 1.06,
}

app = typer.Typer(add_completion=False, help="Build optimizer-ready hourly carbon artifacts.")


@dataclass(frozen=True)
class HourlyCarbonResult:
    countries: tuple[str, ...]
    output_path: Path
    metadata_database: Path
    active_method: ActiveMethod
    source_version: str
    record_count: int
    checksum_sha256: str


def run_hourly_carbon_ingestion(
    countries: str | Sequence[str] = DEFAULT_COUNTRIES,
    output_dir: Path = ROOT_DIR / "data" / "processed" / "subset",
    metadata_database: Path = ROOT_DIR / "data" / "processed" / "source_artifacts.db",
    entsoe_generation_mix: Path | None = None,
    method: str = "auto",
    year: int = DEFAULT_YEAR,
) -> HourlyCarbonResult:
    country_codes = parse_countries(countries)
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    sites = _sites_for_countries(country_codes)
    selected_method = _select_method(method, entsoe_generation_mix)

    if selected_method == "entsoe_hourly_generation_mix":
        records = _build_entsoe_records(country_codes, entsoe_generation_mix)
        source_version = _source_version_for_path(entsoe_generation_mix)
        status = "processed"
        source_status = "preferred"
        fallback = None
    else:
        records = _build_ember_monthly_fallback_records(country_codes, sites, year)
        source_version = "ember-monthly-carbon-fixture-v1"
        status = "fallback_processed"
        source_status = "fallback"
        fallback = "Repeated monthly Ember carbon intensity across each hour in the month."

    output_path = output_dir / "hourly_carbon_subset.json"
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_version": ARTIFACT_VERSION,
        "deterministic_seed": DETERMINISTIC_SEED,
        "generated_at": generated_at,
        "countries": list(country_codes),
        "preferred_method": "entsoe_hourly_generation_mix",
        "fallback_method": "ember_monthly_repeat",
        "active_method": selected_method,
        "source_version": source_version,
        "technology_emission_factors_g_kwh": TECH_EMISSION_FACTORS_G_KWH,
        "records": records,
    }
    checksum = write_json_artifact(output_path, payload)
    summary = ArtifactSummary(
        name="hourly_carbon_subset",
        source="ENTSO-E generation mix / Ember monthly carbon fallback",
        status=status,
        source_status=source_status,
        path=display_path(output_path, ROOT_DIR),
        checksum_sha256=checksum,
        artifact_version=ARTIFACT_VERSION,
        record_count=len(records),
        fallback=fallback,
        notes=(
            "Populates optimizer-ready hourly_energy.carbon_g_kwh values and records "
            "the active calculation method."
        ),
    )
    upsert_source_artifacts(
        metadata_database=metadata_database,
        countries=country_codes,
        generated_at=generated_at,
        artifacts=[summary],
    )
    return HourlyCarbonResult(
        countries=country_codes,
        output_path=output_path,
        metadata_database=metadata_database,
        active_method=selected_method,
        source_version=source_version,
        record_count=len(records),
        checksum_sha256=checksum,
    )


def _select_method(method: str, entsoe_generation_mix: Path | None) -> ActiveMethod:
    # Precedence: an explicit `--method entsoe` is required to require ENTSO-E
    # input; `--method auto` (the default) opportunistically picks ENTSO-E only
    # when the input file is supplied; otherwise we fall back to the Ember
    # monthly broadcast.
    normalized = method.strip().lower()
    if normalized not in {"auto", "entsoe", "ember-monthly-fallback"}:
        raise ValueError("method must be one of: auto, entsoe, ember-monthly-fallback")
    if normalized == "entsoe":
        if entsoe_generation_mix is None:
            raise ValueError("--entsoe-generation-mix is required when --method entsoe is used")
        return "entsoe_hourly_generation_mix"
    if normalized == "auto" and entsoe_generation_mix is not None:
        return "entsoe_hourly_generation_mix"
    return "ember_monthly_repeat"


def _build_entsoe_records(
    countries: Sequence[str],
    entsoe_generation_mix: Path | None,
) -> list[dict[str, object]]:
    if entsoe_generation_mix is None:
        raise ValueError("ENTSO-E generation mix path is required for preferred method.")
    input_records = _load_records(entsoe_generation_mix)
    country_set = set(countries)
    records: list[dict[str, object]] = []
    for record in input_records:
        zone_id = _required_string(record, "zone_id")
        if zone_id not in country_set:
            continue
        timestamp_utc = _required_string(record, "timestamp_utc")
        generation_mix = _generation_mix(record)
        records.append(
            {
                "zone_id": zone_id,
                "timestamp_utc": timestamp_utc,
                "carbon_g_kwh": round(_carbon_from_generation_mix(generation_mix), 3),
                "source_method": "entsoe_hourly_generation_mix",
                "source_version": _source_version_for_path(entsoe_generation_mix),
            }
        )
    if not records:
        raise ValueError(
            "ENTSO-E generation mix input contained no records for requested countries."
        )
    return sorted(records, key=lambda item: (str(item["zone_id"]), str(item["timestamp_utc"])))


def _build_ember_monthly_fallback_records(
    countries: Sequence[str],
    sites: Sequence[SiteFeature],
    year: int,
) -> list[dict[str, object]]:
    monthly_by_country = _monthly_carbon_by_country(sites)
    records: list[dict[str, object]] = []
    for country in countries:
        for timestamp_utc in _iter_year_hours(year):
            month = timestamp_utc.month
            records.append(
                {
                    "zone_id": country,
                    "timestamp_utc": timestamp_utc.isoformat(),
                    "carbon_g_kwh": monthly_by_country[country][month],
                    "source_method": "ember_monthly_repeat",
                    "source_version": "ember-monthly-carbon-fixture-v1",
                    "month": month,
                }
            )
    return records


def _monthly_carbon_by_country(
    sites: Sequence[SiteFeature],
) -> dict[str, dict[int, float]]:
    result: dict[str, dict[int, float]] = {}
    for country in sorted({site.country_code for site in sites}):
        country_sites = [site for site in sites if site.country_code == country]
        base = sum(site.carbon_intensity_g_kwh for site in country_sites) / len(country_sites)
        result[country] = {
            month: round(base * MONTHLY_CARBON_FACTORS[month], 3)
            for month in range(1, 13)
        }
    return result


def _carbon_from_generation_mix(generation_mix_mwh: dict[str, float]) -> float:
    total_mwh = sum(generation_mix_mwh.values())
    if total_mwh <= 0:
        raise ValueError("Generation mix total must be greater than zero.")
    emissions = 0.0
    for technology, generation_mwh in generation_mix_mwh.items():
        factor = TECH_EMISSION_FACTORS_G_KWH[_canonical_technology(technology)]
        emissions += generation_mwh * factor
    return emissions / total_mwh


def _canonical_technology(technology: str) -> str:
    normalized = technology.strip().lower().replace(" ", "_").replace("-", "_")
    aliased = TECH_ALIASES.get(normalized, normalized)
    if aliased in TECH_EMISSION_FACTORS_G_KWH:
        return aliased
    return "other"


def _load_records(path: Path) -> list[dict[str, object]]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw_dict = cast(dict[str, object], raw)
        records_raw: object = raw_dict.get("records")
    else:
        records_raw = raw
    if not isinstance(records_raw, list):
        raise ValueError(f"{path} must contain a list or an object with a records list.")
    records: list[dict[str, object]] = []
    for item in cast(list[object], records_raw):
        if not isinstance(item, dict):
            raise ValueError(f"{path} contains a non-object record.")
        records.append(cast(dict[str, object], item))
    return records


def _generation_mix(record: dict[str, object]) -> dict[str, float]:
    raw = record.get("generation_mix_mwh")
    if not isinstance(raw, dict):
        raise ValueError("ENTSO-E records require generation_mix_mwh.")
    raw_mix = cast(dict[object, object], raw)
    mix: dict[str, float] = {}
    for technology, value in raw_mix.items():
        if not isinstance(technology, str) or not isinstance(value, int | float):
            raise ValueError("generation_mix_mwh must map technology names to numbers.")
        mix[technology] = float(value)
    return mix


def _required_string(record: dict[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Record requires non-empty string field {key}.")
    return value


def _source_version_for_path(path: Path | None) -> str:
    if path is None:
        return "entsoe-generation-mix-unavailable"
    digest = path.read_bytes()
    return f"entsoe-generation-mix-sha256:{hashlib.sha256(digest).hexdigest()}"


def _iter_year_hours(year: int) -> list[datetime]:
    start = datetime(year, 1, 1, tzinfo=UTC)
    hours = 24 * (366 if calendar.isleap(year) else 365)
    return [start + timedelta(hours=offset) for offset in range(hours)]


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
    entsoe_generation_mix: Annotated[
        Path | None,
        typer.Option(
            "--entsoe-generation-mix",
            help="Optional JSON records with zone_id, timestamp_utc, generation_mix_mwh.",
        ),
    ] = None,
    method: Annotated[
        str,
        typer.Option("--method", help="auto, entsoe, or ember-monthly-fallback."),
    ] = "auto",
    year: Annotated[int, typer.Option("--year", help="Fallback calendar year.")] = DEFAULT_YEAR,
) -> None:
    result = run_hourly_carbon_ingestion(
        countries=countries,
        output_dir=output_dir,
        metadata_database=metadata_database,
        entsoe_generation_mix=entsoe_generation_mix,
        method=method,
        year=year,
    )
    typer.echo(f"Wrote hourly carbon artifact: {result.output_path}")
    typer.echo(f"Updated source_artifacts metadata: {result.metadata_database}")
    typer.echo(
        f"- active_method={result.active_method}; records={result.record_count}; "
        f"checksum={result.checksum_sha256[:12]}"
    )


if __name__ == "__main__":
    app()
