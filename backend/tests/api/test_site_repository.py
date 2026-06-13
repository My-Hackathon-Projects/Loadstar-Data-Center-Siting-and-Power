"""Tests for the pipeline-aware site repository.

The repository prefers `data/processed/subset/site_features_subset.json`
(produced by `backend.pipeline.feature_engineering`) and falls back to the
curated `FEATURE_COLLECTION` when that artifact is missing or malformed.
This is the seam where trained `lightgbm_score`, `buildable_fraction`, and
`dc_similarity` reach the scoring engine end-to-end, so it has to be both
correct and resilient.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from backend.api.core.config import get_settings
from backend.api.repositories import site_repository as repo_module
from backend.engine.fixtures import FEATURE_COLLECTION


@pytest.fixture(autouse=True)
def reset_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _reload_repo(monkeypatch: pytest.MonkeyPatch, processed_dir: Path) -> Any:
    """Reload the repository module so it re-reads the artifact path."""

    monkeypatch.setenv("PROCESSED_DATA_DIR", str(processed_dir))
    get_settings.cache_clear()
    return importlib.reload(repo_module)


def test_repository_falls_back_to_fixtures_when_artifact_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An empty processed dir means the API serves the curated fixtures."""

    reloaded = _reload_repo(monkeypatch, tmp_path)
    sites = list(reloaded.site_repository.list_sites())

    assert len(sites) == len(FEATURE_COLLECTION)
    by_id = {site.cell_id: site for site in sites}
    sample = FEATURE_COLLECTION[0]
    assert by_id[sample.cell_id].lightgbm_score == sample.lightgbm_score


def test_repository_loads_pipeline_records_when_artifact_present(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When the artifact exists, the trained values reach the API.

    Repository semantics: the fixture base is preserved (so the static map
    layers cover the full continent) and pipeline records overlay on
    matching `cell_id`s. We only assert the override happened on the cell
    we wrote, not that the full list shrinks to one entry.
    """

    record = FEATURE_COLLECTION[0].model_dump()
    record["lightgbm_score"] = 0.4242
    record["buildable_fraction"] = 0.4343
    record["dc_similarity"] = 0.5151
    artifact = {"records": [record]}
    (tmp_path / "site_features_subset.json").write_text(
        json.dumps(artifact), encoding="utf-8"
    )

    reloaded = _reload_repo(monkeypatch, tmp_path)
    site = reloaded.site_repository.get_site(record["cell_id"])

    assert site is not None
    assert site.lightgbm_score == 0.4242
    assert site.buildable_fraction == 0.4343
    assert site.dc_similarity == 0.5151
    # Other fixture cells must remain available.
    other = reloaded.site_repository.get_site(FEATURE_COLLECTION[1].cell_id)
    assert other is not None


def test_repository_falls_back_when_artifact_is_malformed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A corrupt artifact must not crash the API; fall back to fixtures."""

    (tmp_path / "site_features_subset.json").write_text("{not valid json", encoding="utf-8")

    reloaded = _reload_repo(monkeypatch, tmp_path)
    sites = list(reloaded.site_repository.list_sites())

    assert len(sites) == len(FEATURE_COLLECTION)


def test_repository_falls_back_when_records_array_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A schema regression (no `records` key) must trigger the fallback."""

    (tmp_path / "site_features_subset.json").write_text(
        json.dumps({"schema_version": "v1", "wrong_key": []}),
        encoding="utf-8",
    )

    reloaded = _reload_repo(monkeypatch, tmp_path)
    sites = list(reloaded.site_repository.list_sites())

    assert len(sites) == len(FEATURE_COLLECTION)


def test_repository_skips_invalid_records_but_keeps_valid_ones(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Bad records are dropped record-by-record, not whole-file.

    With the merge semantics, the fixture base remains intact and only the
    valid pipeline record overlays. The two malformed records must not
    crash the load nor pollute any other fixture cell's values.
    """

    valid = FEATURE_COLLECTION[0].model_dump()
    valid["lightgbm_score"] = 0.123
    invalid_missing_field = {"cell_id": "broken", "country_code": "SE"}
    invalid_out_of_range = FEATURE_COLLECTION[1].model_dump()
    invalid_out_of_range["lightgbm_score"] = 5.5  # violates Field(ge=0, le=1)
    artifact = {
        "records": [valid, invalid_missing_field, invalid_out_of_range],
    }
    (tmp_path / "site_features_subset.json").write_text(
        json.dumps(artifact), encoding="utf-8"
    )

    reloaded = _reload_repo(monkeypatch, tmp_path)

    # The good record overrode the matching fixture entry...
    overridden = reloaded.site_repository.get_site(valid["cell_id"])
    assert overridden is not None
    assert overridden.lightgbm_score == 0.123

    # ...the malformed-out-of-range record left its fixture cell intact...
    untouched = reloaded.site_repository.get_site(FEATURE_COLLECTION[1].cell_id)
    assert untouched is not None
    assert untouched.lightgbm_score == FEATURE_COLLECTION[1].lightgbm_score

    # ...and the missing-field record did not appear as a phantom site.
    assert reloaded.site_repository.get_site("broken") is None


def test_repository_get_site_returns_pipeline_record(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """`get_site` reads from the same backing list as `list_sites`."""

    record = FEATURE_COLLECTION[0].model_dump()
    record["lightgbm_score"] = 0.123
    artifact = {"records": [record]}
    (tmp_path / "site_features_subset.json").write_text(
        json.dumps(artifact), encoding="utf-8"
    )

    reloaded = _reload_repo(monkeypatch, tmp_path)
    site = reloaded.site_repository.get_site(record["cell_id"])

    assert site is not None
    assert site.lightgbm_score == 0.123


def test_repository_get_site_returns_none_for_unknown_cell(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    reloaded = _reload_repo(monkeypatch, tmp_path)
    assert reloaded.site_repository.get_site("nope") is None
