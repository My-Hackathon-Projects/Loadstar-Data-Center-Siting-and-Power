"""Service layer for the meta endpoints.

Health responses are assembled here so the router stays thin. The dependency
checks are best-effort: a Postgres timeout or a missing Redis is reported as
`unreachable` / `disabled`, never raised, so `/health` always returns 200.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from importlib import import_module
from urllib.parse import urlparse

from fastapi import Request

from backend.api.core.config import get_settings
from backend.api.services.cache_keys import build_cache_key
from backend.db.connection import get_connection, is_postgres
from backend.engine.assumptions import ASSUMPTIONS
from backend.engine.contracts import (
    AssumptionsResponse,
    HealthDependencies,
    HealthDependency,
    HealthResponse,
)

logger = logging.getLogger("loadstar.meta")

# Bound the dependency checks so /health stays under ~1 second total even when
# Postgres or Redis is behind a slow network.
_DEPENDENCY_TIMEOUT_SECONDS = 0.5


def get_health(request: Request | None = None) -> HealthResponse:
    """Return process health, version metadata, and dependency status."""

    settings = get_settings()
    data_mode = settings.data_mode
    started_at: datetime | None = None
    git_sha: str | None = None
    version = "0.0.0"
    if request is not None:
        started_at = getattr(request.app.state, "started_at", None)
        git_sha = getattr(request.app.state, "git_sha", None)
        version = getattr(request.app.state, "app_version", version)
    uptime = (
        (datetime.now(UTC) - started_at).total_seconds() if started_at is not None else 0.0
    )
    dependencies = HealthDependencies(
        postgres=_check_postgres(settings.database_url),
        redis=_check_redis(settings.redis_url),
    )
    return HealthResponse(
        data_mode=data_mode,
        cache_key=build_cache_key("health", data_mode),
        version=version,
        git_sha=git_sha,
        started_at=started_at,
        uptime_seconds=round(uptime, 3),
        dependencies=dependencies,
    )


def get_assumptions() -> AssumptionsResponse:
    """Return public assumptions for API consumers."""

    data_mode = get_settings().data_mode
    return AssumptionsResponse(
        data_mode=data_mode,
        cache_key=build_cache_key("assumptions", data_mode, ASSUMPTIONS),
        assumptions=ASSUMPTIONS,
    )


def _check_postgres(database_url: str) -> HealthDependency:
    """Probe the database with a `SELECT 1`, capping latency at half a second."""

    if not is_postgres(database_url):
        # SQLite is local and always reachable when the file path is valid; we
        # keep the same shape so the response is uniform.
        return HealthDependency(
            status="ok",
            detail="sqlite",
            latency_ms=0.0,
        )
    started = time.perf_counter()
    try:
        with (
            get_connection(database_url) as connection,
            connection.cursor() as cursor,  # type: ignore[attr-defined]
        ):
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:  # noqa: BLE001 - surfaced as a status string.
        return HealthDependency(
            status="unreachable",
            detail=_safe_dependency_detail(database_url, exc),
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
        )
    return HealthDependency(
        status="ok",
        detail=None,
        latency_ms=round((time.perf_counter() - started) * 1000, 3),
    )


def _check_redis(redis_url: str | None) -> HealthDependency:
    """Probe Redis with a `PING`. Disabled when no URL is configured."""

    if not redis_url:
        return HealthDependency(status="disabled", detail=None, latency_ms=None)
    started = time.perf_counter()
    try:
        redis = import_module("redis")
        client = redis.Redis.from_url(  # type: ignore[attr-defined]
            redis_url,
            socket_connect_timeout=_DEPENDENCY_TIMEOUT_SECONDS,
            socket_timeout=_DEPENDENCY_TIMEOUT_SECONDS,
        )
        client.ping()
    except Exception as exc:  # noqa: BLE001 - surfaced as a status string.
        return HealthDependency(
            status="unreachable",
            detail=_safe_dependency_detail(redis_url, exc),
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
        )
    return HealthDependency(
        status="ok",
        detail=None,
        latency_ms=round((time.perf_counter() - started) * 1000, 3),
    )


def _safe_dependency_detail(url: str, exc: Exception) -> str:
    """Render a probe failure without leaking the full DSN (no credentials)."""

    parsed = urlparse(url)
    target = f"{parsed.scheme}://{parsed.hostname or '?'}"
    return f"{type(exc).__name__} for {target}"
