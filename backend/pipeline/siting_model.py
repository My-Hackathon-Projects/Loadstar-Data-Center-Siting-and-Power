"""Issue 10: train siting propensity and explainable viability scores."""

from __future__ import annotations

import importlib
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast

from backend.pipeline.siting_model_artifacts import write_siting_model_artifacts
from backend.pipeline.siting_model_dataset import (
    build_dataset,
    load_osm_known_data_center_cells,
    load_site_feature_records,
)
from backend.pipeline.siting_model_trainer import fit_siting_model
from backend.pipeline.siting_model_types import SitingModelResult
from backend.pipeline.subset_ingestion import DEFAULT_COUNTRIES, parse_countries

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


def run_siting_model(
    countries: str | Sequence[str] = DEFAULT_COUNTRIES,
    input_dir: Path = ROOT_DIR / "data" / "processed" / "subset",
    output_dir: Path = ROOT_DIR / "data" / "processed" / "subset",
    eval_dir: Path = ROOT_DIR / "eval",
    metadata_database: Path = ROOT_DIR / "data" / "processed" / "source_artifacts.db",
    force_fallback: bool = False,
) -> SitingModelResult:
    country_codes = parse_countries(countries)
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    records = load_site_feature_records(input_dir)
    osm_positive_cells = load_osm_known_data_center_cells(input_dir)
    vectors, examples, dataset_summary = build_dataset(
        records,
        country_codes,
        osm_positive_cells=osm_positive_cells,
    )
    fit = fit_siting_model(
        vectors=vectors,
        examples=examples,
        dataset_summary=dataset_summary,
        force_fallback=force_fallback,
    )
    artifact_write = write_siting_model_artifacts(
        countries=country_codes,
        generated_at=generated_at,
        output_dir=output_dir,
        eval_dir=eval_dir,
        metadata_database=metadata_database,
        fit=fit,
    )
    return SitingModelResult(
        countries=country_codes,
        output_path=artifact_write.output_path,
        metrics_path=artifact_write.metrics_path,
        metadata_database=metadata_database,
        record_count=len(fit.predictions),
        checksum_sha256=artifact_write.checksum_sha256,
        metrics_checksum_sha256=artifact_write.metrics_checksum_sha256,
        source_status=fit.source_status,
    )


def _run_command(
    *,
    countries: str = ",".join(DEFAULT_COUNTRIES),
    input_dir: Path = ROOT_DIR / "data" / "processed" / "subset",
    output_dir: Path = ROOT_DIR / "data" / "processed" / "subset",
    eval_dir: Path = ROOT_DIR / "eval",
    metadata_database: Path = ROOT_DIR / "data" / "processed" / "source_artifacts.db",
    force_fallback: bool = False,
    echo: Callable[[object], None] = print,
) -> None:
    result = run_siting_model(
        countries=countries,
        input_dir=input_dir,
        output_dir=output_dir,
        eval_dir=eval_dir,
        metadata_database=metadata_database,
        force_fallback=force_fallback,
    )
    echo(f"Wrote siting model artifact: {result.output_path}")
    echo(f"Wrote siting model metrics: {result.metrics_path}")
    echo(f"Updated source_artifacts metadata: {result.metadata_database}")
    echo(
        f"- status={result.source_status}; records={result.record_count}; "
        f"checksum={result.checksum_sha256[:12]}"
    )


def main() -> None:
    typer = cast(_TyperModule, importlib.import_module("typer"))
    app = typer.Typer(add_completion=False, help="Train subset siting propensity scores.")

    def command(
        countries: str = ",".join(DEFAULT_COUNTRIES),
        input_dir: Path = ROOT_DIR / "data" / "processed" / "subset",
        output_dir: Path = ROOT_DIR / "data" / "processed" / "subset",
        eval_dir: Path = ROOT_DIR / "eval",
        metadata_database: Path = ROOT_DIR / "data" / "processed" / "source_artifacts.db",
        force_fallback: bool = False,
    ) -> None:
        _run_command(
            countries=countries,
            input_dir=input_dir,
            output_dir=output_dir,
            eval_dir=eval_dir,
            metadata_database=metadata_database,
            force_fallback=force_fallback,
            echo=typer.echo,
        )

    app.callback(invoke_without_command=True)(command)
    app()


if __name__ == "__main__":
    main()
