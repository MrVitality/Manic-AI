"""Scheduled Research Agent service.

Manages a registry of recurring agent jobs. Each job runs `run_agent()` from
`agent_graph` on a configurable interval and ingests the result into a
collection via `ingest_document()`.

Jobs are kept in an in-memory list for fast access and mirrored to Redis so
they survive process restarts. The background loop wakes every 60 seconds,
checks which jobs are due, and fires them as isolated asyncio tasks so a slow
run never blocks the scheduler.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-process job registry
# ---------------------------------------------------------------------------

_jobs: Dict[str, Dict[str, Any]] = {}  # job_id -> job dict
_scheduler_task: Optional[asyncio.Task] = None

# Redis key that stores the full job registry as a JSON blob.
_REDIS_KEY = "scheduler:jobs"


# ---------------------------------------------------------------------------
# Redis helpers (best-effort; fall back gracefully when Redis is unavailable)
# ---------------------------------------------------------------------------

async def _get_redis():
    from api.services.embedding import _redis
    return _redis


async def _persist_to_redis() -> None:
    redis = await _get_redis()
    if not redis:
        return
    try:
        await redis.set(_REDIS_KEY, json.dumps(_jobs, default=str))
    except Exception:
        logger.warning("scheduler: failed to persist jobs to Redis")


async def _load_from_redis() -> None:
    redis = await _get_redis()
    if not redis:
        return
    try:
        raw = await redis.get(_REDIS_KEY)
        if raw:
            loaded = json.loads(raw)
            if isinstance(loaded, dict):
                _jobs.update(loaded)
                logger.info("scheduler: loaded %d job(s) from Redis", len(_jobs))
    except Exception:
        logger.warning("scheduler: failed to load jobs from Redis")


# ---------------------------------------------------------------------------
# Job CRUD
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_job(
    query: str,
    interval_minutes: int,
    collection_id: Optional[str] = None,
    enabled: bool = True,
) -> Dict[str, Any]:
    """Create and register a new scheduled job. Returns the job dict."""
    if interval_minutes < 1:
        raise ValueError("interval_minutes must be >= 1")

    job_id = str(uuid4())
    job: Dict[str, Any] = {
        "id": job_id,
        "query": query,
        "interval_minutes": interval_minutes,
        "collection_id": collection_id,
        "enabled": enabled,
        "last_run": None,
        "created_at": _now_iso(),
    }
    _jobs[job_id] = job
    await _persist_to_redis()
    logger.info("scheduler: created job %s (every %d min)", job_id, interval_minutes)
    return job


def list_jobs() -> List[Dict[str, Any]]:
    """Return all registered jobs as a list."""
    return list(_jobs.values())


async def delete_job(job_id: str) -> bool:
    """Remove a job by ID. Returns True if found and removed."""
    if job_id not in _jobs:
        return False
    del _jobs[job_id]
    await _persist_to_redis()
    logger.info("scheduler: deleted job %s", job_id)
    return True


# ---------------------------------------------------------------------------
# Job execution
# ---------------------------------------------------------------------------

def _is_due(job: Dict[str, Any]) -> bool:
    """Return True if the job has never run or its interval has elapsed."""
    last_run = job.get("last_run")
    if not last_run:
        return True
    try:
        last_dt = datetime.fromisoformat(last_run)
        elapsed_minutes = (datetime.now(timezone.utc) - last_dt).total_seconds() / 60
        return elapsed_minutes >= job["interval_minutes"]
    except (ValueError, TypeError):
        return True


async def _execute_job(
    job: Dict[str, Any],
    http_client: httpx.AsyncClient,
    db_pool: Any,
) -> None:
    """Run one job: call run_agent, then ingest its answer into the collection."""
    job_id = job["id"]
    query = job["query"]
    collection_id = job.get("collection_id")

    logger.info("scheduler: running job %s — query=%r", job_id, query[:80])
    _jobs[job_id]["last_run"] = _now_iso()

    try:
        from api.services.agent_graph import run_agent

        result = await run_agent(
            query=query,
            http_client=http_client,
            db_pool=db_pool,
        )

        answer: str = result.get("answer", "")
        if not answer:
            logger.warning("scheduler: job %s produced an empty answer", job_id)
            await _persist_to_redis()
            return

        # Ingest the answer as a new document so it becomes searchable.
        from api.schemas.ingest import IngestRequest
        from api.services.ingestion import ingest_document

        ingest_req = IngestRequest(
            content=answer,
            filename=f"scheduled_research_{job_id[:8]}.txt",
            content_type="text/plain",
            collection_id=collection_id,
            metadata={
                "source": "scheduled_agent",
                "job_id": job_id,
                "query": query,
                "generated_at": _now_iso(),
            },
        )
        await ingest_document(ingest_req, db_pool, http_client)
        logger.info("scheduler: job %s completed and ingested answer", job_id)

    except Exception:
        logger.exception("scheduler: job %s failed", job_id)
    finally:
        await _persist_to_redis()


# ---------------------------------------------------------------------------
# Background scheduler loop
# ---------------------------------------------------------------------------

async def _scheduler_loop(http_client: httpx.AsyncClient, db_pool: Any) -> None:
    """Infinite loop that fires due jobs every 60 seconds."""
    logger.info("scheduler: background loop started")

    # Give the app a moment to finish startup before the first check.
    await asyncio.sleep(5)

    # Load any jobs persisted from a previous run.
    await _load_from_redis()

    while True:
        try:
            due = [j for j in _jobs.values() if j.get("enabled") and _is_due(j)]
            if due:
                logger.info("scheduler: %d job(s) due this tick", len(due))
                for job in due:
                    # Fire each job as its own task so they run concurrently
                    # and a single slow job cannot block the others.
                    asyncio.create_task(
                        _execute_job(job, http_client, db_pool),
                        name=f"scheduler-job-{job['id'][:8]}",
                    )
        except Exception:
            logger.exception("scheduler: unexpected error in loop")

        await asyncio.sleep(60)


def start_scheduler(http_client: httpx.AsyncClient, db_pool: Any) -> asyncio.Task:
    """Start the background scheduler task and return it for lifecycle management."""
    global _scheduler_task
    _scheduler_task = asyncio.create_task(
        _scheduler_loop(http_client, db_pool),
        name="scheduler-loop",
    )
    return _scheduler_task


async def stop_scheduler() -> None:
    """Cancel the background scheduler task gracefully."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
    _scheduler_task = None
    logger.info("scheduler: background loop stopped")
