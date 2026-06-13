"""Dataset construction for the siting propensity model."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from backend.pipeline.siting_model_types import (
    CURATED_KNOWN_DC_CELLS,
    DETERMINISTIC_SEED,
    FEATURE_COLUMNS,
    NEGATIVES_PER_POSITIVE,
    OSM_POSITIVE_SIMILARITY_THRESHOLD,
    CellFeatureVector,
    TrainingExample,
)


def load_site_feature_records(input_dir: Path) -> list[dict[str, object]]:
    path = input_dir / "site_features_subset.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run backend.pipeline.feature_engineering before siting_model."
        )
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    records = cast(dict[str, object], raw).get("records")
    if not isinstance(records, list):
        raise ValueError(f"{path} must contain a records array.")
    record_items = cast(list[object], records)
    parsed = [cast(dict[str, object], item) for item in record_items if isinstance(item, dict)]
    if not parsed:
        raise ValueError(f"{path} contains no usable site feature records.")
    return parsed


def load_osm_known_data_center_cells(input_dir: Path) -> frozenset[str]:
    path = input_dir / "osm_site_feature_layers.json"
    if not path.exists():
        return frozenset()
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    records = cast(dict[str, object], raw).get("records")
    if not isinstance(records, list):
        return frozenset()
    cells: set[str] = set()
    for item in cast(list[object], records):
        if not isinstance(item, dict):
            continue
        record = cast(dict[str, object], item)
        if record.get("asset_type") != "known_data_center_proxy":
            continue
        cell_id = record.get("cell_id")
        similarity = _optional_float(record.get("similarity_score"))
        if isinstance(cell_id, str) and (
            similarity is None or similarity >= OSM_POSITIVE_SIMILARITY_THRESHOLD
        ):
            cells.add(cell_id)
    return frozenset(cells)


def build_dataset(
    records: Sequence[dict[str, object]],
    countries: Sequence[str],
    osm_positive_cells: frozenset[str] = frozenset(),
) -> tuple[list[CellFeatureVector], list[TrainingExample], dict[str, object]]:
    country_codes = tuple(countries)
    holdout_country = _holdout_country(country_codes)
    vectors = [
        _cell_vector(record, holdout_country, osm_positive_cells) for record in records
    ]
    positives = [_positive_example(vector) for vector in vectors if _is_positive(vector)]
    if not positives:
        raise ValueError("Cannot train siting model without positive cells.")
    negative_candidates = [
        vector for vector in vectors if vector.label != 1 and not vector.excluded
    ]
    if not negative_candidates:
        raise ValueError("Cannot train siting model without negative candidate cells.")
    negatives = _negative_examples(positive_count=len(positives), candidates=negative_candidates)
    examples = [*positives, *negatives]
    label_summary = {
        "positive_count": len(positives),
        "negative_count": len(negatives),
        "negative_positive_ratio": round(len(negatives) / len(positives), 4),
        "positive_sources": sorted({example.label_source for example in positives}),
        "negative_source": "deterministic_non_excluded_cell_sampling",
        "osm_positive_cell_count": len(osm_positive_cells),
    }
    split_summary = {
        "method": "holdout_country",
        "holdout_country": holdout_country,
        "train_count": sum(1 for example in examples if example.split == "train"),
        "heldout_count": sum(1 for example in examples if example.split == "heldout"),
    }
    return vectors, examples, {"labels": label_summary, "split": split_summary}


def _cell_vector(
    record: dict[str, object],
    holdout_country: str,
    osm_positive_cells: frozenset[str],
) -> CellFeatureVector:
    cell_id = _required_string(record.get("cell_id"), "cell_id")
    country_code = _required_string(record.get("country_code"), "country_code")
    region_name = _required_string(record.get("region_name"), "region_name")
    feature_values = _feature_values(record)
    label_source = _positive_source(record, cell_id, osm_positive_cells)
    excluded = _optional_bool(record.get("exclusion_flag"))
    return CellFeatureVector(
        cell_id=cell_id,
        country_code=country_code,
        region_name=region_name,
        feature_values=feature_values,
        split="heldout" if country_code == holdout_country else "train",
        label=1 if label_source else None,
        label_source=label_source,
        excluded=excluded,
    )


def _feature_values(record: dict[str, object]) -> dict[str, float]:
    normalized = record.get("normalized_score_inputs")
    normalized_values = cast(dict[str, object], normalized) if isinstance(normalized, dict) else {}
    values: dict[str, float] = {}
    for feature in FEATURE_COLUMNS:
        source = normalized_values if feature in normalized_values else record
        values[feature] = _clamp01(_required_float(source.get(feature), feature))
    return values


def _positive_source(
    record: dict[str, object],
    cell_id: str,
    osm_positive_cells: frozenset[str],
) -> str | None:
    if cell_id in CURATED_KNOWN_DC_CELLS:
        return "curated_known_data_center_cell"
    if cell_id in osm_positive_cells:
        return "osm_known_data_center_proxy"
    if osm_positive_cells:
        return None
    dc_similarity = _required_float(record.get("dc_similarity"), "dc_similarity")
    if dc_similarity >= OSM_POSITIVE_SIMILARITY_THRESHOLD:
        return "feature_dc_similarity_proxy"
    return None


def _is_positive(vector: CellFeatureVector) -> bool:
    return vector.label == 1


def _positive_example(vector: CellFeatureVector) -> TrainingExample:
    if vector.label_source is None:
        raise ValueError(f"Positive vector {vector.cell_id} is missing label source.")
    return TrainingExample(
        example_id=f"{vector.cell_id}:positive",
        cell_id=vector.cell_id,
        country_code=vector.country_code,
        label=1,
        split=vector.split,
        feature_values=vector.feature_values,
        label_source=vector.label_source,
    )


def _negative_examples(
    *,
    positive_count: int,
    candidates: Sequence[CellFeatureVector],
) -> list[TrainingExample]:
    target_count = positive_count * NEGATIVES_PER_POSITIVE
    ordered = sorted(candidates, key=lambda vector: _stable_sort_key(vector.cell_id))
    examples: list[TrainingExample] = []
    for index in range(target_count):
        vector = ordered[index % len(ordered)]
        examples.append(
            TrainingExample(
                example_id=f"{vector.cell_id}:negative:{index}",
                cell_id=vector.cell_id,
                country_code=vector.country_code,
                label=0,
                split=vector.split,
                feature_values=vector.feature_values,
                label_source="deterministic_non_excluded_cell_sampling",
            )
        )
    return examples


def _holdout_country(countries: Sequence[str]) -> str:
    country_codes = sorted(set(countries))
    if not country_codes:
        raise ValueError("At least one country is required for geography-based split.")
    return country_codes[DETERMINISTIC_SEED % len(country_codes)]


def _stable_sort_key(value: str) -> str:
    return hashlib.sha256(f"{DETERMINISTIC_SEED}:{value}".encode()).hexdigest()


def _required_string(value: object, field_name: str) -> str:
    if isinstance(value, str) and value:
        return value
    raise ValueError(f"Expected non-empty string field {field_name}.")


def _required_float(value: object, field_name: str) -> float:
    parsed = _optional_float(value)
    if parsed is not None:
        return parsed
    raise ValueError(f"Expected numeric field {field_name}.")


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _optional_bool(value: object) -> bool:
    return value if isinstance(value, bool) else False


def _clamp01(value: float) -> float:
    return min(max(value, 0.0), 1.0)
