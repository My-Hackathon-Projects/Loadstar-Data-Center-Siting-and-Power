"""Supply-mix optimization endpoints.

Two paths share the same engine + cache:

- `POST /optimize/supply-mix`: synchronous; the demo path uses this.
- `POST /optimize/supply-mix/async`: returns 202 with a `job_id` immediately;
  the LP runs in a `BackgroundTasks` callback and writes
  `optimization_runs.status` so `GET /optimize/jobs/{id}` can be polled for
  the final response.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, status

from backend.api.routers.errors import key_error_message, not_found, unprocessable
from backend.api.services.optimizer_jobs import (
    enqueue_supply_mix,
    get_job,
    run_supply_mix_job,
)
from backend.api.services.optimizer_service import optimize_site_supply
from backend.engine.contracts import (
    ApiErrorResponse,
    OptimizationJobAccepted,
    OptimizationJobStatus,
    OptimizeRequest,
    SupplyMixResponse,
)

router = APIRouter(prefix="/optimize", tags=["optimizer"])
OPTIMIZER_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ApiErrorResponse},
    422: {"model": ApiErrorResponse},
}


@router.post(
    "/supply-mix",
    response_model=SupplyMixResponse,
    responses=OPTIMIZER_ERROR_RESPONSES,
)
def optimize(request: OptimizeRequest) -> SupplyMixResponse:
    """Return a chart-ready single-site supply-mix optimization response."""

    try:
        return optimize_site_supply(request)
    except KeyError as exc:
        raise not_found(key_error_message(exc), code="site_not_found") from exc
    except RuntimeError as exc:
        raise unprocessable(str(exc), code="optimization_infeasible") from exc


@router.post(
    "/supply-mix/async",
    response_model=OptimizationJobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def optimize_async(
    request: OptimizeRequest,
    background_tasks: BackgroundTasks,
) -> OptimizationJobAccepted:
    """Schedule the LP solve in the background and return the job id immediately."""

    accepted = enqueue_supply_mix(request)
    background_tasks.add_task(run_supply_mix_job, accepted.job_id, request)
    return accepted


@router.get(
    "/jobs/{job_id}",
    response_model=OptimizationJobStatus,
    responses={404: {"model": ApiErrorResponse}},
)
def optimizer_job_status(job_id: str) -> OptimizationJobStatus:
    """Return the persisted state for a previously enqueued job."""

    job = get_job(job_id)
    if job is None:
        raise not_found(f"Unknown optimizer job: {job_id}", code="optimizer_job_not_found")
    return job
