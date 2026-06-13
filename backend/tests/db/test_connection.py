from backend.db.connection import normalize_postgres_url


def test_normalize_postgres_url_removes_vercel_supabase_client_params() -> None:
    dsn = (
        "postgres://user:pass@aws-1-us-east-1.pooler.supabase.com:6543/postgres"
        "?sslmode=require&pgbouncer=true&connection_limit=1"
    )

    assert normalize_postgres_url(dsn) == (
        "postgres://user:pass@aws-1-us-east-1.pooler.supabase.com:6543/postgres"
        "?sslmode=require"
    )


def test_normalize_postgres_url_preserves_supported_libpq_params() -> None:
    dsn = (
        "postgresql://user:pass@example.com/loadstar"
        "?sslmode=require&connect_timeout=3&application_name=loadstar"
    )

    assert normalize_postgres_url(dsn) == dsn


def test_normalize_postgres_url_leaves_non_postgres_urls_unchanged() -> None:
    dsn = "sqlite:///data/loadstar.db?timeout=5"

    assert normalize_postgres_url(dsn) == dsn
