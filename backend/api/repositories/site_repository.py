"""Site repository that prefers pipeline output, falls back to fixtures.

Reads `data/processed/subset/site_features_subset.json` when present; this is
the artifact produced by the LightGBM siting model + AlphaEarth land
pipeline (`backend.pipeline.feature_engineering`). Each record is validated
against `SiteFeature`, so the trained `lightgbm_score`, `buildable_fraction`,
and `dc_similarity` reach the scoring engine end-to-end.

When the artifact is missing, malformed, or stale, the repository falls back
to the curated `FEATURE_COLLECTION` so the demo never breaks (mirroring the
"deterministic fallback" pattern used by the LLM and TTS services). The
fallback is logged at startup so operators can tell which dataset is live.

The interface (`list_sites`, `get_site`) is unchanged; every existing
service, router, and test continues to work without modification.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from pydantic import ValidationError

from backend.api.core.config import get_settings
from backend.engine.contracts import SiteFeature
from backend.engine.fixtures import FEATURE_COLLECTION

logger = logging.getLogger("loadstar.repository")

LAYERABLE_SITE_FIELDS = frozenset(
    {
        "mean_price_eur_mwh",
        "carbon_intensity_g_kwh",
        "congestion_index",
        "headroom_mw",
        "dist_fiber_km",
        "buildable_fraction",
    }
)

# Fields the API contract requires that the pipeline artifact does not always
# emit (it adds extras like normalized_score_inputs, source_methods, …).
# Pydantic ignores unknown keys by default; we only need to make sure every
# *required* SiteFeature field is present in each record before validating.
_REQUIRED_FIELDS: frozenset[str] = frozenset(SiteFeature.model_fields.keys())


def _pipeline_artifact_path() -> Path:
    """Resolve the pipeline output path from settings."""

    return get_settings().processed_data_dir / "site_features_subset.json"


def _load_pipeline_records(path: Path) -> list[SiteFeature] | None:
    """Parse the feature-engineering artifact into validated SiteFeature rows.

    Returns ``None`` (signals "use fixture fallback") on missing file, parse
    error, schema violation, or zero records. Each branch logs why so the
    operator sees in the structured logs which path served traffic.
    """

    if not path.exists():
        logger.info(
            "repository.fixture_fallback",
            extra={
                "event": "repository.fixture_fallback",
                "reason": "artifact_missing",
                "path": str(path),
            },
        )
        return None

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "repository.artifact_unreadable",
            extra={
                "event": "repository.artifact_unreadable",
                "reason": type(exc).__name__,
                "path": str(path),
            },
        )
        return None

    if not isinstance(raw, dict):
        logger.warning(
            "repository.artifact_unreadable",
            extra={
                "event": "repository.artifact_unreadable",
                "reason": "not_an_object",
                "path": str(path),
            },
        )
        return None
    payload = cast(dict[str, object], raw)
    raw_records = payload.get("records")
    if not isinstance(raw_records, list):
        logger.warning(
            "repository.artifact_unreadable",
            extra={
                "event": "repository.artifact_unreadable",
                "reason": "missing_records_array",
                "path": str(path),
            },
        )
        return None

    sites: list[SiteFeature] = []
    rejected = 0
    for raw_record in cast(list[object], raw_records):
        if not isinstance(raw_record, dict):
            rejected += 1
            continue
        record = cast(dict[str, object], raw_record)
        # Skip silently if a required field is absent — keeps the pipeline
        # free to add new top-level keys without breaking the API.
        if not _REQUIRED_FIELDS.issubset(record.keys()):
            rejected += 1
            continue
        try:
            sites.append(SiteFeature.model_validate(record))
        except ValidationError as exc:
            rejected += 1
            logger.warning(
                "repository.record_validation_error",
                extra={
                    "event": "repository.record_validation_error",
                    "cell_id": record.get("cell_id"),
                    "error_count": len(exc.errors()),
                },
            )

    if not sites:
        logger.warning(
            "repository.artifact_empty",
            extra={
                "event": "repository.artifact_empty",
                "rejected": rejected,
                "path": str(path),
            },
        )
        return None

    logger.info(
        "repository.pipeline_loaded",
        extra={
            "event": "repository.pipeline_loaded",
            "site_count": len(sites),
            "rejected": rejected,
            "path": str(path),
        },
    )
    return sites


class SiteRepository:
    """Prefer pipeline output; fall back to the curated fixtures."""

    def __init__(self, sites: Sequence[SiteFeature]) -> None:
        self._sites = list(sites)

    def list_sites(self) -> Sequence[SiteFeature]:
        return self._sites

    def get_site(self, cell_id: str) -> SiteFeature | None:
        return next((site for site in self._sites if site.cell_id == cell_id), None)


def _build_default_repository() -> SiteRepository:
    """Construct the singleton repository at import time."""

    pipeline_sites = _load_pipeline_records(_pipeline_artifact_path())
    if pipeline_sites is not None:
        return SiteRepository(pipeline_sites)
    logger.info(
        "repository.fixture_active",
        extra={
            "event": "repository.fixture_active",
            "site_count": len(FEATURE_COLLECTION),
        },
    )
    return SiteRepository(FEATURE_COLLECTION)


# Backwards-compatible alias so existing imports keep working unchanged.
FixtureSiteRepository = SiteRepository

site_repository = _build_default_repository()
