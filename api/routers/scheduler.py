"""Scheduler routes -- manage recurring research agent jobs.

Endpoints
---------
POST   /v1/agent/schedule        Create a new scheduled job
GET    /v1/agent/schedules       List all scheduled jobs
DELETE /v1/agent/schedule/{id}   Remove a scheduled job
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.schemas.envelope import ok
from api.services import scheduler as svc

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CreateScheduleRequest(BaseModel):
    """Body for POST /v1/agent/schedule."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=10_000,
        description="The research question the agent will run on each interval.",
    )
    interval_minutes: int = Field(
        ...,
        ge=1,
        le=10_080,  # maximum 1 week
        description="How often (in minutes) the job should fire.",
    )
    collection_id: Optional[str] = Field(
        None,
        description="Target collection for ingesting agent answers. Null = default.",
    )
    enabled: bool = Field(True, description="Whether the job starts active.")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/agent/schedule", response_model=None, tags=["agent"])
async def create_schedule(body: CreateScheduleRequest):
    """Create a new recurring research agent job."""
    try:
        job = await svc.create_job(
            query=body.query,
            interval_minutes=body.interval_minutes,
            collection_id=body.collection_id,
            enabled=body.enabled,
        )
        return ok(job)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        logger.exception("Failed to create scheduled job")
        raise HTTPException(status_code=500, detail="Failed to create scheduled job")


@router.get("/agent/schedules", response_model=None, tags=["agent"])
async def list_schedules():
    """Return all registered scheduled jobs."""
    jobs = svc.list_jobs()
    return ok(jobs, meta={"count": len(jobs)})


@router.delete("/agent/schedule/{job_id}", response_model=None, tags=["agent"])
async def delete_schedule(job_id: str):
    """Delete a scheduled job by ID."""
    removed = await svc.delete_job(job_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    return ok({"id": job_id, "deleted": True})
