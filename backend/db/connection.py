"""Database connection helper that picks the right driver from `database_url`.

SQLite remains supported for offline-only smoke tests; Postgres is the default
for `make dev`, `make migrate`, and CI. The helper hides driver selection so
callers (db.migrate, future repository implementations) work against either.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from urllib.parse import urlparse


def parse_scheme(database_url: str) -> str:
    """Return the lowercase scheme component (e.g. `sqlite`, `postgresql`)."""

    return urlparse(database_url).scheme.lower()


def is_postgres(database_url: str) -> bool:
    """True if `database_url` targets Postgres (any psycopg-compatible scheme)."""

    return parse_scheme(database_url).startswith(("postgres", "postgresql"))


def is_sqlite(database_url: str) -> bool:
    """True if `database_url` targets a SQLite file."""

    return parse_scheme(database_url).startswith("sqlite")


def _sqlite_path(database_url: str) -> str:
    # `sqlite:///absolute/path` and `sqlite:////absolute/path` both decode
    # cleanly via urlparse; for relative paths Settings already resolves
    # against ROOT_DIR so the URL we see is always absolute.
    parsed = urlparse(database_url)
    if parsed.netloc:
        # sqlite://host/path is unusual but we surface it for debugging.
        raise ValueError(f"Unsupported sqlite URL with host component: {database_url!r}")
    return parsed.path or database_url.removeprefix("sqlite:///")


@contextmanager
def get_connection(database_url: str) -> Iterator[Any]:
    """Yield a DB-API connection for the schema in `database_url`.

    Caller is responsible for `commit()` (Postgres) or relies on the SQLite
    context-manager auto-commit.
    """

    if is_sqlite(database_url):
        path = _sqlite_path(database_url)
        with sqlite3.connect(path) as connection:
            yield connection
        return

    if is_postgres(database_url):
        # Lazy import: psycopg is a runtime dep, but importing it inside the
        # branch keeps `from backend.db.connection import ...` cheap when the
        # caller only needs the predicates above (e.g. tests deciding which
        # branch to exercise).
        import psycopg

        with psycopg.connect(database_url) as connection:
            yield connection
        return

    raise ValueError(f"Unsupported database_url scheme: {database_url!r}")
