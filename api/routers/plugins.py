"""Plugin management routes."""

import asyncio
import inspect
import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.plugins import get_tool, list_tools
from api.schemas.envelope import ok

logger = logging.getLogger(__name__)

router = APIRouter()


class ToolRunRequest(BaseModel):
    """Request body for running a plugin tool."""

    arguments: Dict[str, Any] = {}


@router.get("/plugins", response_model=None, tags=["plugins"])
async def list_plugins() -> Dict[str, Any]:
    """List all installed plugins and their registered tools."""
    tools = list_tools()
    return ok({"tools": tools, "count": len(tools)})


@router.post("/plugins/{tool_name}/run", response_model=None, tags=["plugins"])
async def run_tool(tool_name: str, body: ToolRunRequest) -> Dict[str, Any]:
    """Execute a plugin tool with the given arguments.

    The tool is called with the arguments from the request body.
    Both sync and async tools are supported.
    """
    fn = get_tool(tool_name)
    if fn is None:
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{tool_name}' not found. Use GET /v1/plugins to list available tools.",
        )

    try:
        if inspect.iscoroutinefunction(fn):
            result = await fn(**body.arguments)
        else:
            result = await asyncio.to_thread(fn, **body.arguments)
    except TypeError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid arguments for tool '{tool_name}': {exc}") from exc
    except Exception as exc:
        logger.exception("Tool '%s' execution failed", tool_name)
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {exc}") from exc

    return ok({"tool": tool_name, "result": result})
