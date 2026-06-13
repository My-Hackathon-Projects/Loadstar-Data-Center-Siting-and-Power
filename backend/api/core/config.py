"""Runtime configuration for the Loadstar API and pipeline CLIs.

Settings are sourced from the root `.env` file; environment variables override.
The same `Settings` instance is consumed by FastAPI and the Typer-based pipeline
CLIs so there is one place to look for defaults.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# `Path(__file__).resolve().parents[3]` walks: core -> api -> backend -> repo root.
ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_DATABASE_URL = "postgresql://loadstar:loadstar@localhost:5432/loadstar"


class Settings(BaseSettings):
    """Runtime settings shared by the API and the pipeline CLIs."""

    app_name: str = "Loadstar API"
    api_environment: str = "development"
    data_mode: str = "fixture"
    logging_level: str = "INFO"
    # `json` for production parsing, `text` for human-readable demo logs. Set via
    # `LOG_FORMAT` in `.env`. JSON is the default so request_id correlation works.
    log_format: Literal["json", "text"] = "json"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"],
    )

    # Postgres DSN. Set DATABASE_URL in `.env` to your local cluster, e.g.
    # `postgresql://loadstar:loadstar@localhost:5432/loadstar`. The default below
    # matches the docker-run snippet in README; override it as needed.
    database_url: str = Field(default=DEFAULT_DATABASE_URL)
    postgres_url: str | None = None

    # Optional Redis for the result-cache layer. When unset, the optimizer cache
    # falls back to the in-process LRU. See `backend/api/services/result_cache.py`.
    redis_url: str | None = None

    # OpenAI integration for the agent/explain endpoint and the chat panel.
    # `openai_enabled` defaults to False; the chat falls back to the deterministic
    # template when the flag is off, the key is missing, or the API errors.
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_enabled: bool = Field(default=False, alias="LOADSTAR_LLM_ENABLED")

    # ElevenLabs text-to-speech for Fred. The API key stays server-side; the
    # frontend receives only generated audio bytes from `/agent/speech`.
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ELEVENLABS_VOICE_ID", "ELEVEBLABS_VOICE_ID"),
    )
    elevenlabs_model: str = "eleven_multilingual_v2"
    elevenlabs_output_format: str = "mp3_44100_128"
    elevenlabs_timeout_seconds: float = 15.0

    # Ember credentials consumed by the access-check CLI. Surfaced here so secrets
    # live in `Settings`, not in scattered `os.getenv` calls.
    ember_api_key: str | None = None
    ember_hourly_price_url: str | None = None

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
        populate_by_name=True,
    )

    @model_validator(mode="after")
    def apply_platform_database_url_fallback(self) -> Self:
        """Use Vercel/Supabase `POSTGRES_URL` when `DATABASE_URL` is not set."""

        if self.database_url == DEFAULT_DATABASE_URL and self.postgres_url:
            self.database_url = self.postgres_url
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""

    return Settings()
