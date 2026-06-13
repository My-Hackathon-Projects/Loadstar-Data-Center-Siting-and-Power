"""Issue 9: build AlphaEarth land features for subset cells."""

from __future__ import annotations

import importlib
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast

from backend.engine.contracts import SiteFeature
from backend.pipeline.alphaearth_land_artifacts import write_land_artifacts
from backend.pipeline.alphaearth_land_earth_engine import run_earth_engine_land_model
from backend.pipeline.alphaearth_land_labels import load_labels
from backend.pipeline.alphaearth_land_outputs import (
    fallback_label_predictions,
    fallback_records,
)
from backend.pipeline.alphaearth_land_types import AlphaEarthLandResult, LandLabelPoint
from backend.pipeline.subset_ingestion import (
    DEFAULT_COUNTRIES,
    FIXTURE_SITES,
    parse_countries,
)

ROOT_DIR = Path(__file__).resolve().parents[2]


class _TyperApp(Protocol):
    def callback(
        self,
        *args: object,
        **kwargs: object,
    ) -> Callable[[Callable[..., object]], Callable[..., object]]: ...

    def __call__(self) -> object: ...


class _TyperModule(Protocol):
    def Typer(self, *args: object, **kwargs: object) -> _TyperApp: ...

    def echo(self, message: object) -> None: ...


def run_alphaearth_land_model(
    countries: str | Sequence[str] = DEFAULT_COUNTRIES,
    output_dir: Path = ROOT_DIR / "data" / "processed" / "subset",
    eval_dir: Path = ROOT_DIR / "eval",
    metadata_database: Path = ROOT_DIR / "data" / "processed" / "source_artifacts.db",
    earthengine_project: str | None = None,
    label_path: Path | None = None,
    allow_fallback: bool = True,
) -> AlphaEarthLandResult:
    country_codes = parse_countries(countries)
    sites = _sites_for_countries(country_codes)
    labels = load_labels(label_path, sites)
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")

    records, heldout_predictions, source_status, active_method, fallback, earthengine_error = (
        _model_outputs(
            sites=sites,
            labels=labels,
            earthengine_project=earthengine_project,
            allow_fallback=allow_fallback,
        )
    )

    artifact_write = write_land_artifacts(
        countries=country_codes,
        generated_at=generated_at,
        output_dir=output_dir,
        eval_dir=eval_dir,
        metadata_database=metadata_database,
        source_status=source_status,
        active_method=active_method,
        fallback=fallback,
        earthengine_error=earthengine_error,
        records=records,
        heldout_predictions=heldout_predictions,
        labels=labels,
        sites=sites,
    )
    return AlphaEarthLandResult(
        countries=country_codes,
        output_path=artifact_write.output_path,
        metrics_path=artifact_write.metrics_path,
        metadata_database=metadata_database,
        record_count=len(records),
        checksum_sha256=artifact_write.checksum_sha256,
        metrics_checksum_sha256=artifact_write.metrics_checksum_sha256,
        source_status=source_status,
    )


def _model_outputs(
    *,
    sites: Sequence[SiteFeature],
    labels: Sequence[LandLabelPoint],
    earthengine_project: str | None,
    allow_fallback: bool,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    str,
    str,
    str | None,
    str | None,
]:
    if not earthengine_project:
        return _fallback_outputs(sites, labels)
    try:
        records, heldout_predictions = run_earth_engine_land_model(
            sites=sites,
            labels=labels,
            earthengine_project=earthengine_project,
        )
        return records, heldout_predictions, "earth_engine", "alphaearth_random_forest", None, None
    except Exception as exc:
        if not allow_fallback:
            raise
        records, heldout_predictions, source_status, active_method, fallback, _ = _fallback_outputs(
            sites,
            labels,
        )
        return records, heldout_predictions, source_status, active_method, fallback, str(exc)


def _fallback_outputs(
    sites: Sequence[SiteFeature],
    labels: Sequence[LandLabelPoint],
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    str,
    str,
    str,
    None,
]:
    fallback = "Earth Engine project or package unavailable; using fixture land proxy."
    return (
        fallback_records(sites),
        fallback_label_predictions(labels, sites),
        "fallback",
        "fixture_land_proxy",
        fallback,
        None,
    )


def _sites_for_countries(countries: Sequence[str]) -> list[SiteFeature]:
    country_set = set(countries)
    sites = [site for site in FIXTURE_SITES if site.country_code in country_set]
    if not sites:
        raise ValueError(f"No fixture cells exist for requested countries: {', '.join(countries)}")
    return sites


def _run_command(
    *,
    countries: str = ",".join(DEFAULT_COUNTRIES),
    output_dir: Path = ROOT_DIR / "data" / "processed" / "subset",
    eval_dir: Path = ROOT_DIR / "eval",
    metadata_database: Path = ROOT_DIR / "data" / "processed" / "source_artifacts.db",
    earthengine_project: str | None = None,
    label_path: Path | None = None,
    allow_fallback: bool = True,
    echo: Callable[[object], None] = print,
) -> None:
    result = run_alphaearth_land_model(
        countries=countries,
        output_dir=output_dir,
        eval_dir=eval_dir,
        metadata_database=metadata_database,
        earthengine_project=earthengine_project,
        label_path=label_path,
        allow_fallback=allow_fallback,
    )
    echo(f"Wrote AlphaEarth land artifact: {result.output_path}")
    echo(f"Wrote AlphaEarth metrics: {result.metrics_path}")
    echo(f"Updated source_artifacts metadata: {result.metadata_database}")
    echo(
        f"- status={result.source_status}; records={result.record_count}; "
        f"checksum={result.checksum_sha256[:12]}"
    )


def main() -> None:
    typer = cast(_TyperModule, importlib.import_module("typer"))
    app = typer.Typer(add_completion=False, help="Build AlphaEarth land features for subset cells.")

    def command(
        countries: str = ",".join(DEFAULT_COUNTRIES),
        output_dir: Path = ROOT_DIR / "data" / "processed" / "subset",
        eval_dir: Path = ROOT_DIR / "eval",
        metadata_database: Path = ROOT_DIR / "data" / "processed" / "source_artifacts.db",
        earthengine_project: str | None = None,
        label_path: Path | None = None,
        allow_fallback: bool = True,
    ) -> None:
        _run_command(
            countries=countries,
            output_dir=output_dir,
            eval_dir=eval_dir,
            metadata_database=metadata_database,
            earthengine_project=earthengine_project,
            label_path=label_path,
            allow_fallback=allow_fallback,
            echo=typer.echo,
        )

    app.callback(invoke_without_command=True)(command)
    app()


if __name__ == "__main__":
    main()
