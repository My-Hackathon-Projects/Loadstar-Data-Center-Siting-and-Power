"""Earth Engine adapter for the AlphaEarth land pipeline."""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from typing import Any, cast

from backend.engine.contracts import SiteFeature
from backend.pipeline.alphaearth_land_types import (
    ALPHAEARTH_COLLECTION_ID,
    ALPHAEARTH_YEAR,
    DETERMINISTIC_SEED,
    EMBEDDING_BANDS,
    H3_PROXY_BUFFER_METERS,
    RANDOM_FOREST_TREES,
    LandLabelPoint,
)
from backend.pipeline.alphaearth_land_utils import (
    clamp01,
    optional_float,
    optional_int,
    optional_string,
    required_float,
    required_string,
)


def run_earth_engine_land_model(
    *,
    sites: Sequence[SiteFeature],
    labels: Sequence[LandLabelPoint],
    earthengine_project: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    ee = _load_earth_engine()
    ee.Initialize(project=earthengine_project)

    cell_features = _cell_features(ee, sites)
    label_features = _label_features(ee, labels)
    embedding = _embedding_image(ee, cell_features)
    samples = embedding.sampleRegions(
        collection=label_features,
        properties=[
            "label_id",
            "cell_id",
            "country_code",
            "buildable_label",
            "dc_label",
            "split",
            "label_source",
        ],
        scale=10,
        tileScale=4,
        geometries=True,
    )
    training_samples = samples.filter(ee.Filter.eq("split", "train"))
    heldout_samples = samples.filter(ee.Filter.eq("split", "heldout"))

    buildable_model = _random_forest_regressor(ee, training_samples, "buildable_label")
    dc_model = _random_forest_regressor(ee, training_samples, "dc_label")
    land_image = _land_prediction_image(embedding, buildable_model, dc_model)

    reduced = land_image.reduceRegions(
        collection=cell_features,
        reducer=ee.Reducer.mean(),
        scale=10,
        tileScale=4,
        maxPixelsPerRegion=2_000_000,
    )
    records = _records_from_earth_engine(reduced.getInfo())

    heldout_scored = heldout_samples.classify(buildable_model, "buildable_prediction").classify(
        dc_model,
        "dc_prediction",
    )
    heldout_predictions = _heldout_predictions_from_earth_engine(heldout_scored.getInfo())
    return records, heldout_predictions


def _load_earth_engine() -> Any:
    return importlib.import_module("ee")


def _cell_features(ee: Any, sites: Sequence[SiteFeature]) -> Any:
    return ee.FeatureCollection(
        [
            ee.Feature(
                ee.Geometry.Point([site.longitude, site.latitude])
                .buffer(H3_PROXY_BUFFER_METERS)
                .bounds(),
                {
                    "cell_id": site.cell_id,
                    "country_code": site.country_code,
                    "region_name": site.region_name,
                    "latitude": site.latitude,
                    "longitude": site.longitude,
                    "resolution": site.resolution,
                },
            )
            for site in sites
        ]
    )


def _label_features(ee: Any, labels: Sequence[LandLabelPoint]) -> Any:
    return ee.FeatureCollection(
        [
            ee.Feature(
                ee.Geometry.Point([label.longitude, label.latitude]),
                {
                    "label_id": label.label_id,
                    "cell_id": label.cell_id,
                    "country_code": label.country_code,
                    "buildable_label": label.buildable_label,
                    "dc_label": label.dc_label,
                    "split": label.split,
                    "label_source": label.label_source,
                },
            )
            for label in labels
        ]
    )


def _embedding_image(ee: Any, cell_features: Any) -> Any:
    return (
        ee.ImageCollection(ALPHAEARTH_COLLECTION_ID)
        .filterDate(f"{ALPHAEARTH_YEAR}-01-01", f"{ALPHAEARTH_YEAR + 1}-01-01")
        .filterBounds(cell_features.geometry())
        .mosaic()
        .select(list(EMBEDDING_BANDS))
    )


def _random_forest_regressor(ee: Any, training_samples: Any, class_property: str) -> Any:
    return (
        ee.Classifier.smileRandomForest(
            numberOfTrees=RANDOM_FOREST_TREES,
            seed=DETERMINISTIC_SEED,
        )
        .setOutputMode("REGRESSION")
        .train(
            features=training_samples,
            classProperty=class_property,
            inputProperties=list(EMBEDDING_BANDS),
        )
    )


def _land_prediction_image(embedding: Any, buildable_model: Any, dc_model: Any) -> Any:
    buildable_image = embedding.classify(buildable_model).rename("buildable_fraction")
    dc_image = embedding.classify(dc_model).rename("dc_similarity")
    return buildable_image.addBands(dc_image).clamp(0, 1)


def _records_from_earth_engine(payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, dict):
        raise ValueError("Earth Engine reduceRegions returned a non-object payload.")
    payload_dict = cast(dict[str, object], payload)
    features = payload_dict.get("features")
    if not isinstance(features, list):
        raise ValueError("Earth Engine reduceRegions returned no features.")

    records: list[dict[str, object]] = []
    for feature in cast(list[object], features):
        if not isinstance(feature, dict):
            continue
        feature_dict = cast(dict[str, object], feature)
        properties = feature_dict.get("properties")
        if not isinstance(properties, dict):
            continue
        records.append(_record_from_properties(cast(dict[str, object], properties)))
    if not records:
        raise ValueError("Earth Engine reduceRegions produced zero usable cell records.")
    return records


def _record_from_properties(props: dict[str, object]) -> dict[str, object]:
    return {
        "cell_id": required_string(props.get("cell_id"), "cell_id"),
        "country_code": required_string(props.get("country_code"), "country_code"),
        "region_name": required_string(props.get("region_name"), "region_name"),
        "latitude": required_float(props.get("latitude"), "latitude"),
        "longitude": required_float(props.get("longitude"), "longitude"),
        "resolution": int(required_float(props.get("resolution"), "resolution")),
        "buildable_fraction": round(_prediction_value(props, "buildable_fraction"), 4),
        "dc_similarity": round(_prediction_value(props, "dc_similarity"), 4),
        "source_method": "alphaearth_random_forest",
        "model_output_status": "earth_engine",
    }


def _prediction_value(props: dict[str, object], field_name: str) -> float:
    return clamp01(required_float(props.get(field_name), field_name))


def _heldout_predictions_from_earth_engine(payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, dict):
        return []
    payload_dict = cast(dict[str, object], payload)
    features = payload_dict.get("features")
    if not isinstance(features, list):
        return []

    predictions: list[dict[str, object]] = []
    for feature in cast(list[object], features):
        if not isinstance(feature, dict):
            continue
        feature_dict = cast(dict[str, object], feature)
        properties = feature_dict.get("properties")
        if not isinstance(properties, dict):
            continue
        predictions.append(_heldout_prediction_from_properties(cast(dict[str, object], properties)))
    return predictions


def _heldout_prediction_from_properties(props: dict[str, object]) -> dict[str, object]:
    return {
        "label_id": optional_string(props.get("label_id"), "missing"),
        "cell_id": optional_string(props.get("cell_id"), "missing"),
        "buildable_label": optional_int(props.get("buildable_label")),
        "dc_label": optional_int(props.get("dc_label")),
        "buildable_prediction": optional_float(props.get("buildable_prediction")),
        "dc_prediction": optional_float(props.get("dc_prediction")),
        "source_method": "alphaearth_random_forest",
    }
