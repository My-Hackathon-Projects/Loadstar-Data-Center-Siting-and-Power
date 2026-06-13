"""Write the FastAPI OpenAPI schema to a local JSON file."""

import json
from pathlib import Path
from typing import Annotated

import typer

from backend.api.main import app


def write_openapi_schema(output: Path) -> None:
    """Write the application OpenAPI schema to `output`."""

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")


def main(
    output: Annotated[
        Path,
        typer.Option("--output", help="Path where the OpenAPI JSON schema should be written."),
    ],
) -> None:
    """CLI entry point for schema generation."""

    write_openapi_schema(output)


if __name__ == "__main__":
    typer.run(main)
