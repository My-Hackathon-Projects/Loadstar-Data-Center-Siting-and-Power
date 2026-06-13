"""Background-task path for the optimizer.

`POST /optimize/supply-mix/async` returns 202 immediately with a `job_id` and
schedules the LP solve as a FastAPI `BackgroundTasks` callback. The callback
writes pending → running → completed/failed rows in `optimization_runs` so
clients can poll `GET /optimize/jobs/{id}` for status and the final response.

Design notes:

- Job state is persisted in `optimization_runs` (Postgres). The 003 migration
  adds `status`, `started_at`, `completed_at`, `solve_ms`, `error_message`,
  and `request_id`.
- Idempotency: before inserting a new pending row, we look up any prior
  completed row for the same `cache_key` and return its job id immediately.
  Two identical async POSTs therefore produce one solve and one row.
- Single-process worker: `BackgroundTasks` runs in the same uvicorn worker.
  Multi-node deployments swap this module for an arq/Celery worker reading
  the same table; the API surface stays unchanged.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from backend.api.core.config import get_settings
from backend.api.middleware.request_id import get_request_id
from backend.api.services.cache_keys import build_cache_key
from backend.api.services.optimizer_service import optimize_site_supply
from backend.db.connection import get_connection
from backend.engine.contracts import (
    ApiErrorDetail,
    OptimizationJobAccepted,
    OptimizationJobStatus,
    OptimizeRequest,
    SupplyMixResponse,
)

logger = logging.getLogger("loadstar.optimizer.jobs")

_STATUS_PATH = "/optimize/jobs/{job_id}"


def enqueue_supply_mix(request: OptimizeRequest) -> OptimizationJobAccepted:
    """Insert a pending job (or return an existing completed one). Idempotent on cache_key."""

    cache_key = build_cache_key("optimize.supply_mix", request)
    settings = get_settings()
    request_id = get_request_id()
    existing = _find_completed_job_id(settings.database_url, cache_key)
    if existing is not None:
        logger.info(
            "optimize.job_idempotent_hit",
            extra={
                "event": "optimize.job_idempotent_hit",
                "job_id": existing,
                "cache_key": cache_key,
            },
        )
        return OptimizationJobAccepted(
            job_id=existing,
            status_url=_STATUS_PATH.format(job_id=existing),
            status="pending",
            cache_key=cache_key,
        )

    job_id = uuid.uuid4().hex
    _insert_pending(
        settings.database_url,
        job_id=job_id,
        cell_id=request.cell_id,
        load_mw=request.load_mw,
        request_payload=request.model_dump(mode="json"),
        cache_key=cache_key,
        request_id=request_id,
    )
    logger.info(
        "optimize.job_queued",
        extra={
            "event": "optimize.job_queued",
            "job_id": job_id,
            "cache_key": cache_key,
        },
    )
    return OptimizationJobAccepted(
        job_id=job_id,
        status_url=_STATUS_PATH.format(job_id=job_id),
        status="pending",
        cache_key=cache_key,
    )


def run_supply_mix_job(job_id: str, request: OptimizeRequest) -> None:
    """BackgroundTasks callback: solve the LP, update the row, never raise."""

    settings = get_settings()
    started = datetime.now(UTC)
    started_perf = time.perf_counter()
    _update_status(
        settings.database_url,
        job_id=job_id,
        status="running",
        started_at=started.isoformat(),
    )
    try:
        response = optimize_site_supply(request)
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started_perf) * 1000, 3)
        message = str(exc) or type(exc).__name__
        logger.warning(
            "optimize.job_failed",
            extra={
                "event": "optimize.job_failed",
                "job_id": job_id,
                "error": type(exc).__name__,
                "solve_ms": elapsed_ms,
            },
        )
        _update_status(
            settings.database_url,
            job_id=job_id,
            status="failed",
            completed_at=datetime.now(UTC).isoformat(),
            error_message=message,
            solve_ms=elapsed_ms,
        )
        return

    elapsed_ms = round((time.perf_counter() - started_perf) * 1000, 3)
    _update_status(
        settings.database_url,
        job_id=job_id,
        status="completed",
        completed_at=datetime.now(UTC).isoformat(),
        result_payload=response.model_dump(mode="json"),
        solve_ms=elapsed_ms,
    )
    logger.info(
        "optimize.job_completed",
        extra={
            "event": "optimize.job_completed",
            "job_id": job_id,
            "solve_ms": elapsed_ms,
            "solver_status": response.solver_status,
        },
    )


def get_job(job_id: str) -> OptimizationJobStatus | None:
    """Fetch the row for `job_id`, or None if it does not exist."""

    settings = get_settings()
    row = _select_row(settings.database_url, job_id=job_id)
    if row is None:
        return None
    return _row_to_status(row)


def _find_completed_job_id(database_url: str, cache_key: str) -> str | None:
    query = (
        "SELECT run_id FROM optimization_runs "
        "WHERE cache_key = %s AND status = 'completed' LIMIT 1"
    )
    with get_connection(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(query, (cache_key,))
        row = cursor.fetchone()
    if row is None:
        return None
    return str(row[0])


def _insert_pending(
    database_url: str,
    *,
    job_id: str,
    cell_id: str,
    load_mw: float,
    request_payload: dict[str, Any],
    cache_key: str,
    request_id: str | None,
) -> None:
    query = (
        "INSERT INTO optimization_runs ("
        "run_id, cell_id, load_mw, request_json, result_json, cache_key, "
        "status, started_at, request_id"
        ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
    )
    request_blob = json.dumps(request_payload, sort_keys=True)
    started_at = datetime.now(UTC).isoformat()
    args = (
        job_id,
        cell_id,
        float(load_mw),
        request_blob,
        "{}",  # result_json filled when the job completes.
        cache_key,
        "pending",
        started_at,
        request_id,
    )
    with get_connection(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, args)
        connection.commit()


def _update_status(
    database_url: str,
    *,
    job_id: str,
    status: str,
    started_at: str | None = None,
    completed_at: str | None = None,
    result_payload: dict[str, Any] | None = None,
    error_message: str | None = None,
    solve_ms: float | None = None,
) -> None:
    fields: list[str] = ["status = %s"]
    args: list[Any] = [status]
    if started_at is not None:
        fields.append("started_at = %s")
        args.append(started_at)
    if completed_at is not None:
        fields.append("completed_at = %s")
        args.append(completed_at)
    if result_payload is not None:
        fields.append("result_json = %s")
        args.append(json.dumps(result_payload, sort_keys=True))
    if error_message is not None:
        fields.append("error_message = %s")
        args.append(error_message)
    if solve_ms is not None:
        fields.append("solve_ms = %s")
        args.append(solve_ms)
    args.append(job_id)
    query = "UPDATE optimization_runs SET " + ", ".join(fields) + " WHERE run_id = %s"
    with get_connection(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, args)
        connection.commit()


def _select_row(database_url: str, *, job_id: str) -> dict[str, Any] | None:
    columns = (
        "run_id",
        "cache_key",
        "status",
        "started_at",
        "completed_at",
        "result_json",
        "error_message",
        "solve_ms",
        "request_id",
    )
    query = (
        f"SELECT {', '.join(columns)} FROM optimization_runs "
        "WHERE run_id = %s"
    )
    with get_connection(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(query, (job_id,))
        row = cursor.fetchone()
    if row is None:
        return None
    return dict(zip(columns, row, strict=False))


def _row_to_status(row: dict[str, Any]) -> OptimizationJobStatus:
    result_payload: SupplyMixResponse | None = None
    raw_result = row.get("result_json")
    if raw_result and raw_result not in {"{}", ""}:
        try:
            parsed = json.loads(raw_result)
            if isinstance(parsed, dict) and "cell_id" in parsed:
                result_payload = SupplyMixResponse.model_validate(parsed)
        except (json.JSONDecodeError, ValueError):
            result_payload = None
    error: ApiErrorDetail | None = None
    error_message = row.get("error_message")
    if error_message:
        error = ApiErrorDetail(code="optimization_failed", message=error_message)
    return OptimizationJobStatus(
        job_id=row["run_id"],
        status=row["status"],
        cache_key=row["cache_key"],
        request_id=row.get("request_id"),
        started_at=_stringify_timestamp(row.get("started_at")),
        completed_at=_stringify_timestamp(row.get("completed_at")),
        solve_ms=row.get("solve_ms"),
        result=result_payload,
        error=error,
    )


def _stringify_timestamp(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
