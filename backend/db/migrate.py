"""Apply the Postgres schema (initial + subsequent migrations) from zero.

Loadstar uses Postgres only. This module is a thin runner that applies every
`*.sql` file under `backend/db/` in lexicographic order against the Postgres
DSN provided via `--database-url` or `Settings.database_url`.

Migrations are idempotent: every file uses `CREATE TABLE IF NOT EXISTS` and
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` so re-running is safe.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from backend.api.core.config import get_settings
from backend.db.connection import get_connection, is_postgres

ROOT_DIR = Path(__file__).resolve().parents[2]
SCHEMA_DIR = Path(__file__).resolve().parent


def _migration_files() -> list[Path]:
    """Return every numbered Postgres migration in order."""

    return sorted(SCHEMA_DIR.glob("[0-9][0-9][0-9]_*.sql"))


def apply_schema_url(database_url: str) -> None:
    """Apply every migration to `database_url`. Postgres only."""

    if not is_postgres(database_url):
        raise ValueError(
            f"Unsupported database_url scheme: {database_url!r}. Loadstar requires Postgres."
        )
    files = _migration_files()
    with get_connection(database_url) as connection:
        for path in files:
            schema_sql = path.read_text(encoding="utf-8")
            with connection.cursor() as cursor:
                cursor.execute(schema_sql)
            connection.commit()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply the Loadstar Postgres schema from zero (idempotent).",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Postgres DSN (postgresql://...). Defaults to Settings.database_url.",
    )
    args = parser.parse_args()
    database_url = args.database_url or get_settings().database_url
    apply_schema_url(database_url)
    print(f"Applied schema to {database_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
