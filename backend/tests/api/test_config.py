import pytest

from backend.api.core.config import Settings


def test_postgres_url_fills_database_url_when_database_url_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supabase_url = "postgresql://user:pass@supabase.example:5432/postgres"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_URL", supabase_url)

    settings = Settings(_env_file=None)

    assert settings.database_url == supabase_url


def test_database_url_takes_precedence_over_postgres_url(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = "postgresql://user:pass@primary.example:5432/loadstar"
    supabase_url = "postgresql://user:pass@supabase.example:5432/postgres"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("POSTGRES_URL", supabase_url)

    settings = Settings(_env_file=None)

    assert settings.database_url == database_url
