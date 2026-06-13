"""Read-only access to the `source_artifacts` SQLite table.

The pipeline CLIs write rows here (one per artifact, including manifests and
fallback markers); the API reads them so consumers can answer two operational
questions: "which sources are populating the demo right now?" and "has the
data slice changed since the last reload?". Read-only on purpose: the API
must never mutate ingestion metadata.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from backend.api.core.config import get_settings
from backend.api.services.cache_keys import build_cache_key
from backend.engine.contracts import SourceArtifact, SourceArtifactsResponse

logger = logging.getLogger("loadstar.source_artifacts")

# Stable list of columns matches the schema created by
# `backend/pipeline/artifacts.py::upsert_source_artifacts`.
_SELECT_COLUMNS: tuple[str, ...] = (
    "artifact_name",
    "country_scope",
    "artifact_version",
    "source_name",
    "source_status",
    "status",
    "checksum_sha256",
    "artifact_path",
    "record_count",
    "fallback",
    "generated_at",
    "metadata_json",
)


def get_source_artifacts(
    artifact_name: str | None = None,
    country: str | None = None,
) -> SourceArtifactsResponse:
    """Return the artifact rows, optionally filtered by name or country code."""

    settings = get_settings()
    rows = _load_rows(
        Path(settings.source_artifacts_db),
        artifact_name=artifact_name,
        country=country,
    )
    artifacts = [_row_to_artifact(row) for row in rows]
    data_version = _data_version(artifacts)
    cache_key = build_cache_key(
        "meta.source_artifacts",
        artifact_name or "",
        country or "",
        data_version,
        len(artifacts),
    )
    return SourceArtifactsResponse(
        data_mode=settings.data_mode,
        cache_key=cache_key,
        data_version=data_version,
        artifact_count=len(artifacts),
        artifacts=artifacts,
    )


def _load_rows(
    database_path: Path,
    *,
    artifact_name: str | None,
    country: str | None,
) -> list[sqlite3.Row]:
    """Open the metadata DB read-only and return the matching rows.

    A missing or empty database returns no rows rather than raising so an
    operator can hit `/meta/source-artifacts` before any pipeline has ever run.
    """

    if not database_path.exists():
        logger.warning(
            "source_artifacts.missing",
            extra={"event": "source_artifacts.missing", "path": str(database_path)},
        )
        return []
    uri = f"file:{database_path.resolve()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as connection:
            connection.row_factory = sqlite3.Row
            return _query(connection, artifact_name=artifact_name, country=country)
    except sqlite3.DatabaseError as exc:
        logger.warning(
            "source_artifacts.unreadable",
            extra={
                "event": "source_artifacts.unreadable",
                "path": str(database_path),
                "error": type(exc).__name__,
            },
        )
        return []


def _query(
    connection: sqlite3.Connection,
    *,
    artifact_name: str | None,
    country: str | None,
) -> list[sqlite3.Row]:
    columns = ", ".join(_SELECT_COLUMNS)
    sql = f"SELECT {columns} FROM source_artifacts"  # noqa: S608 - column list is constant.
    clauses: list[str] = []
    params: list[Any] = []
    if artifact_name:
        clauses.append("artifact_name = ?")
        params.append(artifact_name)
    if country:
        clauses.append("(country_scope = ? OR instr(',' || country_scope || ',', ?) > 0)")
        params.append(country)
        params.append(f",{country},")
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY artifact_name, country_scope"
    cursor = connection.execute(sql, params)
    return list(cursor.fetchall())


def _row_to_artifact(row: sqlite3.Row) -> SourceArtifact:
    metadata: dict[str, Any] = {}
    raw_metadata = row["metadata_json"]
    if raw_metadata:
        try:
            parsed = json.loads(raw_metadata)
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict):
            metadata = cast(dict[str, Any], parsed)
    return SourceArtifact(
        artifact_name=row["artifact_name"],
        country_scope=row["country_scope"],
        artifact_version=row["artifact_version"],
        source_name=row["source_name"],
        source_status=row["source_status"],
        status=row["status"],
        checksum_sha256=row["checksum_sha256"],
        artifact_path=row["artifact_path"],
        record_count=row["record_count"],
        fallback=row["fallback"],
        generated_at=row["generated_at"],
        metadata=metadata,
    )


def _data_version(artifacts: Sequence[SourceArtifact]) -> str:
    """Stable 20-char fingerprint over the active checksums."""

    digest = hashlib.sha256(
        ",".join(sorted(artifact.checksum_sha256 for artifact in artifacts)).encode("utf-8")
    ).hexdigest()
    return digest[:20]
