"""Postgres connection helper.

Only Postgres is supported as the application database. The artifact metadata
file at `data/processed/source_artifacts.db` is a separate concern: it is a
local SQLite ledger written by the pipeline CLIs (single writer, file-based,
no service required) and is read by the `/meta/source-artifacts` endpoint.
That file is intentional and not the application DB.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from urllib.parse import urlparse


def parse_scheme(database_url: str) -> str:
    """Return the lowercase scheme component (e.g. `postgresql`)."""

    return urlparse(database_url).scheme.lower()


def is_postgres(database_url: str) -> bool:
    """True if `database_url` targets Postgres (any psycopg-compatible scheme)."""

    return parse_scheme(database_url).startswith(("postgres", "postgresql"))


@contextmanager
def get_connection(database_url: str) -> Iterator[Any]:
    """Yield a psycopg connection for the given Postgres DSN.

    The caller is responsible for `commit()`. Raises `ValueError` if the URL
    is not a Postgres scheme: the API supports only Postgres.
    """

    if not is_postgres(database_url):
        raise ValueError(
            f"Unsupported database_url scheme: {database_url!r}. Loadstar requires Postgres."
        )
    # Lazy import: keeps `from backend.db.connection import is_postgres` cheap.
    import psycopg

    with psycopg.connect(database_url) as connection:
        yield connection
