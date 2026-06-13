import json
import sqlite3
from pathlib import Path
from typing import Any

from backend.pipeline.alphaearth_land import run_alphaearth_land_model
from backend.pipeline.feature_engineering import run_feature_engineering
from backend.pipeline.hourly_carbon import run_hourly_carbon_ingestion
from backend.pipeline.siting_model import run_siting_model
from backend.pipeline.siting_model_trainer import fit_siting_model
from backend.pipeline.siting_model_types import (
    FEATURE_COLUMNS,
    CellFeatureVector,
    TrainingExample,
)
from backend.pipeline.subset_ingestion import run_subset_ingestion


def test_siting_model_outputs_scores_explanations_metrics_and_metadata(tmp_path: Path) -> None:
    output_dir = tmp_path / "processed"
    eval_dir = tmp_path / "eval"
    metadata_database = tmp_path / "source_artifacts.db"
    run_subset_ingestion(
        countries="SE,DE,IE",
        output_dir=output_dir,
        metadata_database=metadata_database,
    )
    run_hourly_carbon_ingestion(
        countries="SE,DE,IE",
        output_dir=output_dir,
        metadata_database=metadata_database,
    )
    run_alphaearth_land_model(
        countries="SE,DE,IE",
        output_dir=output_dir,
        eval_dir=eval_dir,
        metadata_database=metadata_database,
        earthengine_project=None,
    )
    run_feature_engineering(
        countries="SE,DE,IE",
        input_dir=output_dir,
        output_dir=output_dir,
        metadata_database=metadata_database,
    )

    result = run_siting_model(
        countries="SE,DE,IE",
        input_dir=output_dir,
        output_dir=output_dir,
        eval_dir=eval_dir,
        metadata_database=metadata_database,
        force_fallback=True,
    )

    artifact = json.loads(result.output_path.read_text(encoding="utf-8"))
    metrics = json.loads(result.metrics_path.read_text(encoding="utf-8"))
    assert result.record_count == 10
    assert artifact["active_method"] == "transparent_composite"
    assert artifact["deterministic_seed"] == 20260612
    assert 3 <= artifact["label_summary"]["negative_positive_ratio"] <= 5
    assert set(artifact["label_summary"]["positive_sources"]) == {
        "curated_known_data_center_cell",
        "osm_known_data_center_proxy",
    }
    assert metrics["split_strategy"]["method"] == "holdout_country"
    assert metrics["auc"] is not None
    assert metrics["precision_at_k"]
    assert metrics["feature_importance"]
    assert metrics["model_artifact_checksum_sha256"] == result.checksum_sha256

    records_by_cell = {record["cell_id"]: record for record in artifact["records"]}
    for record in records_by_cell.values():
        assert 0 <= record["viability_score"] <= 1
        assert record["shap_values"]
        assert set(record["shap_values"]).issubset(set(artifact["feature_columns"]))

    rerun = run_feature_engineering(
        countries="SE,DE,IE",
        input_dir=output_dir,
        output_dir=output_dir,
        metadata_database=metadata_database,
    )
    feature_payload = json.loads(rerun.output_path.read_text(encoding="utf-8"))
    for record in feature_payload["records"]:
        model_record = records_by_cell[record["cell_id"]]
        assert record["lightgbm_score"] == model_record["viability_score"]
        assert record["shap_values"] == model_record["shap_values"]
        assert record["source_methods"]["ml"] == "transparent_composite"

    with sqlite3.connect(metadata_database) as connection:
        row = connection.execute(
            """
            SELECT checksum_sha256, record_count, source_status
            FROM source_artifacts
            WHERE artifact_name = 'siting_model_subset'
            AND country_scope = 'SE,DE,IE'
            """
        ).fetchone()

    assert row == (result.checksum_sha256, 10, "fallback")


def test_siting_model_lightgbm_path_records_trained_outputs(monkeypatch: Any) -> None:
    class FakeBooster:
        def predict(self, matrix: list[list[float]], pred_contrib: bool = False) -> list[object]:
            if pred_contrib:
                return [[row[0], *[0.0 for _ in FEATURE_COLUMNS[1:]], 0.0] for row in matrix]
            return [0.8 if row[0] >= 0.5 else 0.2 for row in matrix]

        def feature_importance(self, importance_type: str) -> list[float]:
            assert importance_type == "gain"
            return [1.0, *[0.0 for _ in FEATURE_COLUMNS[1:]]]

        def dump_model(self) -> dict[str, object]:
            return {"tree_info": []}

    class FakeLightGBM:
        class Dataset:
            def __init__(
                self,
                data: list[list[float]],
                label: list[int],
                feature_name: list[str],
            ) -> None:
                self.data = data
                self.label = label
                self.feature_name = feature_name

        @staticmethod
        def train(
            params: dict[str, object],
            train_data: "FakeLightGBM.Dataset",
            num_boost_round: int,
        ) -> FakeBooster:
            assert params["objective"] == "binary"
            assert num_boost_round == 40
            assert train_data.feature_name == list(FEATURE_COLUMNS)
            return FakeBooster()

    class FakeNumpy:
        @staticmethod
        def asarray(values: list[object], dtype: str) -> list[object]:
            assert dtype in {"float64", "int8"}
            return values

    def fake_import(name: str) -> object:
        if name == "lightgbm":
            return FakeLightGBM
        if name == "numpy":
            return FakeNumpy
        raise AssertionError(name)

    feature_values = {feature: 0.0 for feature in FEATURE_COLUMNS}
    positive_values = {**feature_values, FEATURE_COLUMNS[0]: 1.0}
    negative_values = {**feature_values, FEATURE_COLUMNS[0]: 0.0}
    vectors = [
        CellFeatureVector(
            cell_id="positive",
            country_code="SE",
            region_name="Positive",
            feature_values=positive_values,
            split="train",
            label=1,
            label_source="curated_known_data_center_cell",
            excluded=False,
        ),
        CellFeatureVector(
            cell_id="negative",
            country_code="DE",
            region_name="Negative",
            feature_values=negative_values,
            split="train",
            label=None,
            label_source=None,
            excluded=False,
        ),
    ]
    examples = [
        TrainingExample(
            example_id="positive:positive",
            cell_id="positive",
            country_code="SE",
            label=1,
            split="train",
            feature_values=positive_values,
            label_source="curated_known_data_center_cell",
        ),
        TrainingExample(
            example_id="negative:negative",
            cell_id="negative",
            country_code="DE",
            label=0,
            split="train",
            feature_values=negative_values,
            label_source="deterministic_non_excluded_cell_sampling",
        ),
    ]

    monkeypatch.setattr(
        "backend.pipeline.siting_model_trainer.importlib.import_module",
        fake_import,
    )

    fit = fit_siting_model(
        vectors=vectors,
        examples=examples,
        dataset_summary={
            "labels": {"positive_count": 1, "negative_count": 1},
            "split": {"method": "holdout_country"},
        },
    )

    assert fit.source_status == "trained"
    assert fit.active_method == "lightgbm"
    assert fit.fallback is None
    assert fit.feature_importance[FEATURE_COLUMNS[0]] == 1.0
    assert [prediction.viability_score for prediction in fit.predictions] == [0.8, 0.2]
    assert fit.predictions[0].shap_values[FEATURE_COLUMNS[0]] == 1.0
