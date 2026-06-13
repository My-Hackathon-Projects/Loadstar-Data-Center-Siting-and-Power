"""Apply the minimal Loadstar schema (plus subsequent migrations) from zero.

`apply_schema(path)` keeps the legacy SQLite-by-path entry point so existing
tests (which create temp files via pytest's `tmp_path`) work unchanged.
`apply_schema_url(url)` is the modern entry point: any `database_url` value
the API would accept is also valid here.

Migrations are applied in lexicographic order. SQLite reads `*_sqlite.sql`
files when present; Postgres reads the dialect-neutral `*.sql` files. The
initial schema (`001_initial.sql`) is SQLite-flavoured and the Postgres-
flavoured equivalent is `002_postgres.sql`; for additive migrations after
that point both dialects coexist as `003_*.sql` and `003_*_sqlite.sql`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from backend.api.core.config import get_settings
from backend.db.connection import get_connection, is_postgres, is_sqlite

ROOT_DIR = Path(__file__).resolve().parents[2]
SCHEMA_DIR = Path(__file__).resolve().parent


def _migration_files(database_url: str) -> list[Path]:
    """Return the migration files to apply, in order, for the given dialect."""

    if is_sqlite(database_url):
        # Initial schema is the SQLite path; later migrations have a `_sqlite`
        # variant. Collect both, drop the Postgres-only `002_*` and any
        # non-sqlite `003+_*` migrations.
        files: list[Path] = []
        for path in sorted(SCHEMA_DIR.glob("[0-9][0-9][0-9]_*.sql")):
            if path.name == "001_initial.sql":
                files.append(path)
                continue
            if path.name == "002_postgres.sql":
                continue
            if path.name.endswith("_sqlite.sql"):
                files.append(path)
        return files
    if is_postgres(database_url):
        files = []
        for path in sorted(SCHEMA_DIR.glob("[0-9][0-9][0-9]_*.sql")):
            if path.name == "001_initial.sql":
                # Replaced by `002_postgres.sql` for Postgres.
                continue
            if path.name.endswith("_sqlite.sql"):
                continue
            files.append(path)
        return files
    raise ValueError(f"Unsupported database_url scheme: {database_url!r}")


def apply_schema(database_path: Path) -> None:
    """Legacy SQLite-by-path entry point. Creates parent dirs if needed."""

    database_path.parent.mkdir(parents=True, exist_ok=True)
    apply_schema_url(f"sqlite:///{database_path.resolve()}")


def apply_schema_url(database_url: str) -> None:
    """Apply every migration appropriate to `database_url`, in order."""

    files = _migration_files(database_url)
    with get_connection(database_url) as connection:
        for path in files:
            schema_sql = path.read_text(encoding="utf-8")
            if is_sqlite(database_url):
                connection.executescript(schema_sql)
                connection.commit()
                continue
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
