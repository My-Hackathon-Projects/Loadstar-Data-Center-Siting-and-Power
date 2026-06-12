from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the Loadstar API."""

    app_name: str = "Loadstar API"
    data_mode: str = "fixture"
    database_url: str = Field(default="sqlite:///data/loadstar.db")
    web_dist_dir: Path = Field(default=Path("web/dist"))

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
