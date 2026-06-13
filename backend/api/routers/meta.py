"""Health, assumptions, and source-artifacts metadata endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from backend.api.services.meta_service import get_assumptions, get_health
from backend.api.services.source_artifacts_service import get_source_artifacts
from backend.engine.contracts import (
    AssumptionsResponse,
    HealthResponse,
    SourceArtifactsResponse,
)

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    """Return process health, version metadata, and dependency status."""

    return get_health(request)


@router.get("/assumptions", response_model=AssumptionsResponse)
def assumptions() -> AssumptionsResponse:
    """Return the public assumptions used by the fixture skeleton."""

    return get_assumptions()


@router.get("/meta/source-artifacts", response_model=SourceArtifactsResponse)
def source_artifacts(
    artifact_name: str | None = Query(default=None, description="Exact artifact name match."),
    country: str | None = Query(
        default=None,
        description="ISO-3166 alpha-2 country code; matches scoped or comma-separated lists.",
    ),
) -> SourceArtifactsResponse:
    """Operational metadata for source versions and ingestion artifacts."""

    return get_source_artifacts(artifact_name=artifact_name, country=country)
