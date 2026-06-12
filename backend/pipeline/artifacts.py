"""Shared artifact-write helpers used by every pipeline CLI.

The three helpers (`write_json_artifact`, `display_path`, `upsert_source_artifacts`)
plus the `ArtifactSummary` dataclass are the canonical way for ingestion code
to produce a JSON artifact and record its checksum/source row in
`source_artifacts.db`. Do not duplicate them.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArtifactSummary:
    name: str
    source: str
    status: str
    source_status: str
    path: str
    checksum_sha256: str
    artifact_version: str
    record_count: int
    fallback: str | None
    notes: str


def write_json_artifact(path: Path, payload: dict[str, object]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.write_text(content, encoding="utf-8")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def display_path(path: Path, root_dir: Path) -> str:
    try:
        return str(path.relative_to(root_dir))
    except ValueError:
        return str(path)


def upsert_source_artifacts(
    *,
    metadata_database: Path,
    countries: Sequence[str],
    generated_at: str,
    artifacts: Sequence[ArtifactSummary],
) -> None:
    metadata_database.parent.mkdir(parents=True, exist_ok=True)
    country_scope = ",".join(countries)
    with sqlite3.connect(metadata_database) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS source_artifacts (
                artifact_name TEXT NOT NULL,
                country_scope TEXT NOT NULL,
                artifact_version TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_status TEXT NOT NULL,
                status TEXT NOT NULL,
                checksum_sha256 TEXT NOT NULL,
                artifact_path TEXT NOT NULL,
                record_count INTEGER NOT NULL,
                fallback TEXT,
                generated_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                PRIMARY KEY (artifact_name, country_scope)
            )
            """
        )
        for artifact in artifacts:
            connection.execute(
                """
                INSERT INTO source_artifacts (
                    artifact_name, country_scope, artifact_version, source_name,
                    source_status, status, checksum_sha256, artifact_path, record_count,
                    fallback, generated_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(artifact_name, country_scope) DO UPDATE SET
                    artifact_version = excluded.artifact_version,
                    source_name = excluded.source_name,
                    source_status = excluded.source_status,
                    status = excluded.status,
                    checksum_sha256 = excluded.checksum_sha256,
                    artifact_path = excluded.artifact_path,
                    record_count = excluded.record_count,
                    fallback = excluded.fallback,
                    generated_at = excluded.generated_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    artifact.name,
                    country_scope,
                    artifact.artifact_version,
                    artifact.source,
                    artifact.source_status,
                    artifact.status,
                    artifact.checksum_sha256,
                    artifact.path,
                    artifact.record_count,
                    artifact.fallback,
                    generated_at,
                    json.dumps({"notes": artifact.notes}, sort_keys=True),
                ),
            )
        connection.commit()
