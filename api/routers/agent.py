"""Agent routes -- stateful Generator-Critic reasoning loop."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import asyncpg
import httpx

from api.dependencies import get_db_optional, get_http_client
from api.schemas.envelope import ok
from api.services.agent_graph import get_run_status, run_agent, stream_agent_steps

logger = logging.getLogger(__name__)

router = APIRouter()


class AgentRunRequest(BaseModel):
    """Request body for POST /v1/agent/run."""

    query: str = Field(..., min_length=1, max_length=10000, description="The question or task for the agent")
    model: Optional[str] = Field(None, description="Override the default chat model")


@router.post("/agent/run", response_model=None, tags=["agent"])
async def agent_run(
    request: AgentRunRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
):
    """Execute the agent Generator-Critic loop and return the structured result."""
    try:
        result = await run_agent(
            query=request.query,
            http_client=client,
            db_pool=db,
            model=request.model,
        )
        return ok(result)
    except httpx.HTTPError:
        logger.exception("Agent run failed: inference backend unavailable")
        raise HTTPException(status_code=502, detail="Inference backend unavailable")
    except Exception:
        logger.exception("Unexpected error during agent run")
        raise HTTPException(status_code=500, detail="Agent run failed")


@router.get("/agent/{run_id}/status", response_model=None, tags=["agent"])
async def agent_status(run_id: str):
    """Check the status of an agent run by its ID."""
    state = await get_run_status(run_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"No agent run found for run_id={run_id}")
    return ok(state)


@router.post("/agent/stream", tags=["agent"])
async def agent_stream(
    request: AgentRunRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
):
    """Stream agent steps in real-time via SSE."""
    return StreamingResponse(
        stream_agent_steps(
            query=request.query,
            http_client=client,
            db_pool=db,
            model=request.model,
        ),
        media_type="text/event-stream",
    )
