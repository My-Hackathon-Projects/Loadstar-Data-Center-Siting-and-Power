from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from api.app.core.config import get_settings
from api.app.routers import meta, optimizer, sites

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Fixture-backed walking skeleton for data-center siting and power planning.",
)

app.include_router(meta.router)
app.include_router(sites.router)
app.include_router(optimizer.router)

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
        "message": "Loadstar API is running. Start the web app with `npm --prefix web run dev`.",
        "docs": "/docs",
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    """Avoid noisy browser 404s during the demo path."""

    return Response(status_code=204)
