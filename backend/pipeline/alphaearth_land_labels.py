"""Deterministic label loading and fixture label sampling for AlphaEarth."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from backend.engine.contracts import SiteFeature
from backend.pipeline.alphaearth_land_types import (
    DETERMINISTIC_SEED,
    TRAIN_FRACTION,
    LandLabelPoint,
    Split,
)
from backend.pipeline.alphaearth_land_utils import (
    optional_string,
    required_binary,
    required_float,
    required_string,
)


def load_labels(
    label_path: Path | None,
    sites: Sequence[SiteFeature],
) -> tuple[LandLabelPoint, ...]:
    if label_path is None:
        return fixture_label_points(sites)
    raw: object = json.loads(label_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{label_path} must contain a JSON object.")
    raw_dict = cast(dict[str, object], raw)
    raw_labels = raw_dict.get("labels")
    if not isinstance(raw_labels, list):
        raise ValueError(f"{label_path} must contain a labels array.")

    labels: list[LandLabelPoint] = []
    site_by_cell = {site.cell_id: site for site in sites}
    for index, item in enumerate(cast(list[object], raw_labels)):
        if not isinstance(item, dict):
            raise ValueError(f"Label {index} must be a JSON object.")
        labels.append(_label_from_json(cast(dict[str, object], item), index, site_by_cell))
    return tuple(labels)


def fixture_label_points(sites: Sequence[SiteFeature]) -> tuple[LandLabelPoint, ...]:
    labels: list[LandLabelPoint] = []
    for site in sites:
        labels.append(
            LandLabelPoint(
                label_id=f"{site.cell_id}:center",
                cell_id=site.cell_id,
                country_code=site.country_code,
                region_name=site.region_name,
                latitude=site.latitude,
                longitude=site.longitude,
                buildable_label=(
                    1 if site.buildable_fraction >= 0.55 and not site.exclusion_flag else 0
                ),
                dc_label=1 if site.dc_similarity >= 0.75 else 0,
                split="train",
                label_source="fixture_cell_center_proxy",
            )
        )
        offset = deterministic_offset(site.cell_id)
        labels.append(
            LandLabelPoint(
                label_id=f"{site.cell_id}:unsuitable-offset",
                cell_id=site.cell_id,
                country_code=site.country_code,
                region_name=site.region_name,
                latitude=round(site.latitude + offset[0], 6),
                longitude=round(site.longitude + offset[1], 6),
                buildable_label=0,
                dc_label=0,
                split="train",
                label_source="fixture_unsuitable_offset_proxy",
            )
        )
    return assign_splits(labels)


def assign_splits(labels: Sequence[LandLabelPoint]) -> tuple[LandLabelPoint, ...]:
    holdout_count = max(1, round(len(labels) * (1 - TRAIN_FRACTION)))
    ordered = sorted(labels, key=lambda label: stable_unit_interval(label.label_id))
    heldout_ids = {label.label_id for label in ordered[:holdout_count]}
    return tuple(
        LandLabelPoint(
            label_id=label.label_id,
            cell_id=label.cell_id,
            country_code=label.country_code,
            region_name=label.region_name,
            latitude=label.latitude,
            longitude=label.longitude,
            buildable_label=label.buildable_label,
            dc_label=label.dc_label,
            split="heldout" if label.label_id in heldout_ids else "train",
            label_source=label.label_source,
        )
        for label in labels
    )


def deterministic_offset(cell_id: str) -> tuple[float, float]:
    unit = stable_unit_interval(cell_id)
    lat_offset = 0.035 + unit * 0.025
    lon_offset = -(0.035 + (1 - unit) * 0.025)
    return lat_offset, lon_offset


def stable_unit_interval(value: str) -> float:
    digest = hashlib.sha256(f"{DETERMINISTIC_SEED}:{value}".encode()).hexdigest()
    return int(digest[:12], 16) / int("f" * 12, 16)


def _label_from_json(
    label: dict[str, object],
    index: int,
    site_by_cell: dict[str, SiteFeature],
) -> LandLabelPoint:
    cell_id = required_string(label.get("cell_id"), "cell_id")
    site = site_by_cell.get(cell_id)
    if site is None:
        raise ValueError(f"Label {index} references unknown subset cell {cell_id!r}.")
    return LandLabelPoint(
        label_id=optional_string(label.get("label_id"), f"manual-{index}"),
        cell_id=cell_id,
        country_code=site.country_code,
        region_name=site.region_name,
        latitude=required_float(label.get("latitude"), "latitude"),
        longitude=required_float(label.get("longitude"), "longitude"),
        buildable_label=required_binary(label.get("buildable_label"), "buildable_label"),
        dc_label=required_binary(label.get("dc_label"), "dc_label"),
        split=_parse_split(label.get("split"), index),
        label_source=optional_string(label.get("label_source"), "manual_map_label"),
    )


def _parse_split(value: object, index: int) -> Split:
    if value in {"train", "heldout"}:
        return cast(Split, value)
    return "heldout" if stable_unit_interval(f"manual:{index}") > TRAIN_FRACTION else "train"
