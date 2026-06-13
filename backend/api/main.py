"""FastAPI application entry point. Mounts routers and the built SPA bundle.

Wires the request-ID middleware (outermost) and CORS (innermost), configures
JSON-structured logging via `core/logging.py`, and stashes process metadata
(`started_at`, `git_sha`) on `app.state` for the `/health` endpoint.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from importlib import metadata as importlib_metadata
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.api.core.config import get_settings
from backend.api.core.logging import configure_logging
from backend.api.middleware.request_id import RequestIdMiddleware
from backend.api.routers import agent, meta, optimizer, sites


def _resolve_git_sha() -> str | None:
    """Best-effort short SHA of HEAD; None outside a git checkout or on error."""

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            check=False,
            cwd=Path(__file__).resolve().parents[2],
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    sha = result.stdout.strip()
    return sha if result.returncode == 0 and sha else None


def _resolve_app_version() -> str:
    """Read the project version from installed metadata, falling back to `0.0.0`."""

    try:
        return importlib_metadata.version("loadstar")
    except importlib_metadata.PackageNotFoundError:
        return "0.0.0"


settings = get_settings()
configure_logging(settings.logging_level, settings.log_format)
logger = logging.getLogger("loadstar.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Stash process metadata at startup; nothing to clean up on shutdown."""

    app.state.started_at = datetime.now(UTC)
    app.state.git_sha = _resolve_git_sha()
    app.state.app_version = _resolve_app_version()
    logger.info(
        "api.startup",
        extra={
            "event": "api.startup",
            "version": app.state.app_version,
            "git_sha": app.state.git_sha,
            "data_mode": settings.data_mode,
        },
    )
    yield


app = FastAPI(
    title=settings.app_name,
    version=_resolve_app_version(),
    description="Fixture-backed walking skeleton for data-center siting and power planning.",
    lifespan=lifespan,
)

# Order matters: request-ID is added first, runs last (outermost). CORS is added
# second, runs first (innermost) so the request-ID is set before CORS rejects.
# Starlette applies middleware in LIFO order from the registration list.
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_credentials=False,
        allow_headers=["*", "X-Request-ID"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_origins=settings.cors_origins,
        expose_headers=["X-Request-ID"],
    )
app.add_middleware(RequestIdMiddleware)

app.include_router(meta.router)
app.include_router(sites.router)
app.include_router(optimizer.router)
app.include_router(agent.router)

web_dist_dir = Path(settings.web_dist_dir)
if web_dist_dir.exists() and (web_dist_dir / "assets").exists():
    app.mount("/assets", StaticFiles(directory=web_dist_dir / "assets"), name="assets")


@app.get("/", include_in_schema=False, response_model=None)
def index() -> FileResponse | dict[str, str]:
    """Serve the built Vite app when available, otherwise point developers to Vite."""

    index_path = web_dist_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {
        "message": (
            "Loadstar API is running. "
            "Start the web app with `npm --prefix frontend run dev`."
        ),
        "docs": "/docs",
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    """Avoid noisy browser 404s during the demo path."""

    return Response(status_code=204)
