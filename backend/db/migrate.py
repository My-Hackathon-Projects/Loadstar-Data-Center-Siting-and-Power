"""Apply the minimal four-table Loadstar schema to SQLite or Postgres from zero.

`apply_schema(path)` keeps the legacy SQLite-by-path entry point so existing
tests (which create temp files via pytest's `tmp_path`) work unchanged.
`apply_schema_url(url)` is the modern entry point: any `database_url` value
the API would accept is also valid here.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from backend.api.core.config import get_settings
from backend.db.connection import get_connection, is_postgres, is_sqlite

ROOT_DIR = Path(__file__).resolve().parents[2]
SQLITE_SCHEMA_PATH = Path(__file__).resolve().parent / "001_initial.sql"
POSTGRES_SCHEMA_PATH = Path(__file__).resolve().parent / "002_postgres.sql"


def _schema_for(database_url: str) -> str:
    """Return the SQL text appropriate to the DSN scheme."""

    if is_sqlite(database_url):
        return SQLITE_SCHEMA_PATH.read_text(encoding="utf-8")
    if is_postgres(database_url):
        return POSTGRES_SCHEMA_PATH.read_text(encoding="utf-8")
    raise ValueError(f"Unsupported database_url scheme: {database_url!r}")


def apply_schema(database_path: Path) -> None:
    """Legacy SQLite-by-path entry point. Creates parent dirs if needed."""

    database_path.parent.mkdir(parents=True, exist_ok=True)
    # Resolve so the URL we hand to urlparse always has a leading slash on
    # the path component, regardless of whether the caller passed a relative
    # or absolute Path. `Path.resolve()` does not require the file to exist.
    apply_schema_url(f"sqlite:///{database_path.resolve()}")


def apply_schema_url(database_url: str) -> None:
    """Apply the schema appropriate to `database_url`."""

    schema_sql = _schema_for(database_url)
    with get_connection(database_url) as connection:
        if is_sqlite(database_url):
            # sqlite3 has executescript() for multi-statement SQL.
            connection.executescript(schema_sql)
            connection.commit()
            return
        # Postgres: psycopg's execute() handles multi-statement SQL when the
        # DSN is opened without server-side cursors (default).
        with connection.cursor() as cursor:
            cursor.execute(schema_sql)
        connection.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply the minimal Loadstar schema from zero.")
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help="SQLite file path. Mutually exclusive with --database-url.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Full DSN (sqlite:///... or postgresql://...). Defaults to Settings.database_url.",
    )
    args = parser.parse_args()

    if args.database and args.database_url:
        parser.error("Pass either --database or --database-url, not both.")

    if args.database:
        apply_schema(args.database)
        print(f"Applied schema to sqlite:///{args.database}")
        return 0

    database_url = args.database_url or get_settings().database_url
    apply_schema_url(database_url)
    print(f"Applied schema to {database_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
