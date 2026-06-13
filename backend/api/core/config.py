"""Runtime configuration for the Loadstar API and pipeline CLIs.

Settings are sourced from the root `.env` file; environment variables override.
The same `Settings` instance is consumed by FastAPI and the Typer-based pipeline
CLIs so there is one place to look for defaults.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# `Path(__file__).resolve().parents[3]` walks: core -> api -> backend -> repo root.
ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Runtime settings shared by the API and the pipeline CLIs."""

    app_name: str = "Loadstar API"
    api_environment: str = "development"
    data_mode: str = "fixture"
    logging_level: str = "INFO"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"],
    )

    # SQLite is the dev default; set DATABASE_URL in `.env` to a Postgres DSN
    # such as `postgresql+psycopg://loadstar:loadstar@localhost:5432/loadstar`
    # when the live Postgres switch lands.
    database_url: str = Field(default=f"sqlite:///{ROOT_DIR / 'data' / 'loadstar.db'}")

    # Where the built Vite bundle lives. The API mounts /assets from here when present.
    web_dist_dir: Path = Field(default=ROOT_DIR / "frontend" / "dist")

    # Pipeline defaults — picked up by the Typer CLIs via `_config.py`.
    processed_data_dir: Path = Field(default=ROOT_DIR / "data" / "processed" / "subset")
    source_artifacts_db: Path = Field(
        default=ROOT_DIR / "data" / "processed" / "source_artifacts.db",
    )

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""

    return Settings()
