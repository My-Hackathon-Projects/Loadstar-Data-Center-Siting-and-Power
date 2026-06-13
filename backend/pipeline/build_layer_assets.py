"""Pre-compute the `/layers/*` GeoJSON responses to static files.

Hosting the overlays as static assets under `frontend/public/layers/` lets the
SPA fetch them straight from a CDN with strong cache headers, with the FastAPI
endpoint as the live fallback. This is the CDN-ready story for the demo: the
overlays are still small (<50 KB), so PMTiles is overkill, but ensuring the
map paint path does not hit the API on every reload is the right hygiene.

When an overlay grows past ~5 MB or ~1000 features, regenerate as
`*.pmtiles` via `tippecanoe` and switch the deck.gl layer to `MVTLayer` /
`pmtiles-protocol`. See README "Limitations" for the migration path.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from backend.api.repositories.site_repository import site_repository
from backend.api.services.meta_service import get_assumptions
from backend.api.services.site_service import ALLOWED_LAYERS, get_layer

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "frontend" / "public" / "layers"
DATA_OUTPUT_DIR = ROOT_DIR / "frontend" / "public" / "data"


def run_layer_assets(output_dir: Path = DEFAULT_OUTPUT_DIR) -> list[Path]:
    """Write one JSON file per layer; return the list of paths written."""

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for layer_name in sorted(ALLOWED_LAYERS):
        response = get_layer(layer_name)
        path = output_dir / f"{layer_name}.json"
        # `model_dump_json` emits exactly what the API returns, so the static
        # asset and the live endpoint are byte-equivalent for client parsing.
        path.write_text(response.model_dump_json(indent=2) + "\n", encoding="utf-8")
        written.append(path)
    return written


def run_assumptions_asset(output_dir: Path = DATA_OUTPUT_DIR) -> Path:
    """Write the `/assumptions` payload as a static asset for the no-API path."""

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "assumptions.json"
    path.write_text(get_assumptions().model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def run_sites_asset(output_dir: Path = DATA_OUTPUT_DIR) -> Path:
    """Write the merged site collection (fixture base + pipeline overlays).

    The frontend `sites.json` is what the local `siteEngine` ranks against.
    Writing the same merged view the API serves keeps the local engine in
    parity with the backend ranking, which the `siteEngine.test.ts` parity
    test asserts cell-for-cell.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "sites.json"
    sites = list(site_repository.list_sites())
    payload = [site.model_dump(mode="json") for site in sites]
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


app = typer.Typer(add_completion=False, help="Build static map-layer assets for the SPA.")


@app.callback(invoke_without_command=True)
def main(
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", help="Directory for the generated GeoJSON layer assets."),
    ] = DEFAULT_OUTPUT_DIR,
) -> None:
    """CLI entry point for `make layer-assets`."""

    paths = run_layer_assets(output_dir=output_dir)
    assumptions_path = run_assumptions_asset()
    sites_path = run_sites_asset()
    typer.echo(f"Wrote {len(paths)} layer assets under {output_dir}")
    for path in paths:
        typer.echo(f"- {path.relative_to(ROOT_DIR)}")
    typer.echo(f"- {assumptions_path.relative_to(ROOT_DIR)}")
    typer.echo(f"- {sites_path.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    app()
