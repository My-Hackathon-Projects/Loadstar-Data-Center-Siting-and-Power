"""Training and deterministic fallback scoring for the siting model."""

from __future__ import annotations

import importlib
import math
import os
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, cast

from backend.pipeline.siting_model_types import (
    DETERMINISTIC_SEED,
    FEATURE_COLUMNS,
    CellFeatureVector,
    SitingPrediction,
    TrainingExample,
)

FALLBACK_WEIGHTS: dict[str, float] = {
    "mean_price_eur_mwh": 0.08,
    "carbon_intensity_g_kwh": 0.09,
    "congestion_index": 0.08,
    "headroom_mw": 0.11,
    "dist_hv_substation_km": 0.08,
    "dist_fiber_km": 0.08,
    "dist_ixp_km": 0.05,
    "latency_proxy_ms": 0.05,
    "solar_cf": 0.05,
    "wind_cf": 0.07,
    "water_dist_km": 0.04,
    "cooling_degree_proxy": 0.04,
    "buildable_fraction": 0.11,
    "dc_similarity": 0.17,
}


@dataclass(frozen=True)
class SitingModelFit:
    source_status: str
    active_method: str
    predictions: list[SitingPrediction]
    metrics: dict[str, object]
    feature_importance: dict[str, float]
    model_payload: dict[str, object]
    fallback: str | None


def fit_siting_model(
    *,
    vectors: Sequence[CellFeatureVector],
    examples: Sequence[TrainingExample],
    dataset_summary: dict[str, object],
    force_fallback: bool = False,
) -> SitingModelFit:
    if force_fallback:
        return _fallback_fit(
            vectors=vectors,
            examples=examples,
            dataset_summary=dataset_summary,
            fallback="Forced transparent composite fallback.",
        )
    try:
        return _lightgbm_fit(vectors=vectors, examples=examples, dataset_summary=dataset_summary)
    except Exception as exc:  # noqa: BLE001 - recorded as model fallback evidence.
        return _fallback_fit(
            vectors=vectors,
            examples=examples,
            dataset_summary=dataset_summary,
            fallback=f"LightGBM unavailable or failed; using transparent composite. Reason: {exc}",
        )


def _lightgbm_fit(
    *,
    vectors: Sequence[CellFeatureVector],
    examples: Sequence[TrainingExample],
    dataset_summary: dict[str, object],
) -> SitingModelFit:
    os.environ.setdefault("MPLCONFIGDIR", f"{tempfile.gettempdir()}/loadstar-matplotlib")
    lgb = cast(Any, importlib.import_module("lightgbm"))
    np = cast(Any, importlib.import_module("numpy"))
    train_examples = [example for example in examples if example.split == "train"]
    if len({example.label for example in train_examples}) < 2:
        raise ValueError("Training split must contain both positive and negative labels.")

    train_matrix = np.asarray(_matrix(train_examples), dtype="float64")
    train_labels = np.asarray([example.label for example in train_examples], dtype="int8")
    train_data = lgb.Dataset(
        train_matrix,
        label=train_labels,
        feature_name=list(FEATURE_COLUMNS),
    )
    params = {
        "objective": "binary",
        "metric": "auc",
        "verbosity": -1,
        "learning_rate": 0.08,
        "num_leaves": 7,
        "max_depth": 3,
        "min_data_in_leaf": 1,
        "min_data_in_bin": 1,
        "min_sum_hessian_in_leaf": 1e-3,
        "feature_pre_filter": False,
        "seed": DETERMINISTIC_SEED,
        "feature_fraction_seed": DETERMINISTIC_SEED,
        "bagging_seed": DETERMINISTIC_SEED,
        "data_random_seed": DETERMINISTIC_SEED,
        "deterministic": True,
        "force_col_wise": True,
    }
    booster = lgb.train(params, train_data, num_boost_round=40)
    vector_matrix = np.asarray(_matrix(vectors), dtype="float64")
    scores = [_clamp01(float(score)) for score in booster.predict(vector_matrix)]
    contributions = _contributions_from_lightgbm(booster.predict(vector_matrix, pred_contrib=True))
    predictions = [
        SitingPrediction(
            cell_id=vector.cell_id,
            country_code=vector.country_code,
            region_name=vector.region_name,
            viability_score=round(score, 4),
            shap_values=contributions[index],
            split=vector.split,
            label=vector.label,
            source_method="lightgbm",
        )
        for index, (vector, score) in enumerate(zip(vectors, scores, strict=True))
    ]
    feature_importance = _feature_importance(
        FEATURE_COLUMNS,
        booster.feature_importance(importance_type="gain"),
    )
    metrics = _metrics(
        predictions=predictions,
        examples=examples,
        dataset_summary=dataset_summary,
        feature_importance=feature_importance,
    )
    return SitingModelFit(
        source_status="trained",
        active_method="lightgbm",
        predictions=predictions,
        metrics=metrics,
        feature_importance=feature_importance,
        model_payload={
            "type": "lightgbm_booster",
            "params": params,
            "num_boost_round": 40,
            "model": booster.dump_model(),
        },
        fallback=None,
    )


def _fallback_fit(
    *,
    vectors: Sequence[CellFeatureVector],
    examples: Sequence[TrainingExample],
    dataset_summary: dict[str, object],
    fallback: str,
) -> SitingModelFit:
    predictions = [
        SitingPrediction(
            cell_id=vector.cell_id,
            country_code=vector.country_code,
            region_name=vector.region_name,
            viability_score=round(_transparent_score(vector.feature_values), 4),
            shap_values=_transparent_contributions(vector.feature_values),
            split=vector.split,
            label=vector.label,
            source_method="transparent_composite",
        )
        for vector in vectors
    ]
    feature_importance = {
        feature: round(weight / sum(FALLBACK_WEIGHTS.values()), 6)
        for feature, weight in FALLBACK_WEIGHTS.items()
    }
    metrics = _metrics(
        predictions=predictions,
        examples=examples,
        dataset_summary=dataset_summary,
        feature_importance=feature_importance,
    )
    return SitingModelFit(
        source_status="fallback",
        active_method="transparent_composite",
        predictions=predictions,
        metrics=metrics,
        feature_importance=feature_importance,
        model_payload={
            "type": "transparent_composite",
            "weights": FALLBACK_WEIGHTS,
            "score_range": [0.0, 1.0],
        },
        fallback=fallback,
    )


def _matrix(items: Sequence[TrainingExample] | Sequence[CellFeatureVector]) -> list[list[float]]:
    return [[item.feature_values[feature] for feature in FEATURE_COLUMNS] for item in items]


def _transparent_score(feature_values: dict[str, float]) -> float:
    weighted = sum(feature_values[feature] * weight for feature, weight in FALLBACK_WEIGHTS.items())
    return _clamp01(weighted / sum(FALLBACK_WEIGHTS.values()))


def _transparent_contributions(feature_values: dict[str, float]) -> dict[str, float]:
    total_weight = sum(FALLBACK_WEIGHTS.values())
    return {
        feature: round((feature_values[feature] - 0.5) * weight / total_weight, 6)
        for feature, weight in FALLBACK_WEIGHTS.items()
    }


def _contributions_from_lightgbm(raw_contributions: object) -> list[dict[str, float]]:
    rows = cast(Sequence[Sequence[object]], raw_contributions)
    contributions: list[dict[str, float]] = []
    for row in rows:
        values = [_coerce_float(value) for value in row[: len(FEATURE_COLUMNS)]]
        contributions.append(
            {
                feature: round(value, 6)
                for feature, value in zip(FEATURE_COLUMNS, values, strict=True)
            }
        )
    return contributions


def _feature_importance(
    feature_columns: Sequence[str],
    raw_importance: object,
) -> dict[str, float]:
    values = [max(0.0, _coerce_float(value)) for value in cast(Sequence[object], raw_importance)]
    total = sum(values)
    if total == 0:
        return {feature: 0.0 for feature in feature_columns}
    return {
        feature: round(value / total, 6)
        for feature, value in zip(feature_columns, values, strict=True)
    }


def _metrics(
    *,
    predictions: Sequence[SitingPrediction],
    examples: Sequence[TrainingExample],
    dataset_summary: dict[str, object],
    feature_importance: dict[str, float],
) -> dict[str, object]:
    label_by_cell = _labels_by_cell(examples)
    scored = [
        (prediction.viability_score, label_by_cell[prediction.cell_id], prediction.cell_id)
        for prediction in predictions
        if prediction.cell_id in label_by_cell
    ]
    return {
        "auc": _auc(scored),
        "precision_at_k": _precision_at_k(scored),
        "feature_importance": feature_importance,
        "label_summary": dataset_summary["labels"],
        "split_strategy": dataset_summary["split"],
    }


def _labels_by_cell(examples: Sequence[TrainingExample]) -> dict[str, int]:
    labels: dict[str, int] = {}
    for example in examples:
        if example.label == 1:
            labels[example.cell_id] = 1
        else:
            labels.setdefault(example.cell_id, 0)
    return labels


def _auc(scored: Sequence[tuple[float, int, str]]) -> float | None:
    positives = [(score, cell_id) for score, label, cell_id in scored if label == 1]
    negatives = [(score, cell_id) for score, label, cell_id in scored if label == 0]
    if not positives or not negatives:
        return None
    wins = 0.0
    total = 0
    for positive_score, _ in positives:
        for negative_score, _ in negatives:
            total += 1
            if positive_score > negative_score:
                wins += 1
            elif math.isclose(positive_score, negative_score):
                wins += 0.5
    return round(wins / total, 4)


def _precision_at_k(scored: Sequence[tuple[float, int, str]]) -> dict[str, float]:
    ordered = sorted(scored, key=lambda item: (-item[0], item[2]))
    positive_count = sum(label for _, label, _ in ordered)
    k_values = sorted({1, min(3, len(ordered)), min(max(positive_count, 1), len(ordered))})
    precision: dict[str, float] = {}
    for k in k_values:
        if k <= 0:
            continue
        precision[f"p@{k}"] = round(sum(label for _, label, _ in ordered[:k]) / k, 4)
    return precision


def _clamp01(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def _coerce_float(value: object) -> float:
    return float(cast(Any, value))
