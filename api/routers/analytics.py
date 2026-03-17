"""Analytics routes."""

from typing import Any, Dict, Optional

import asyncpg
import httpx
from fastapi import APIRouter, Depends, Query

from api.dependencies import get_db_optional, get_http_client
from api.schemas.envelope import ok
from api.services.analytics import (
    model_analytics,
    rag_analytics,
    services_history,
    usage_analytics,
)

router = APIRouter()

_PERIOD_INTERVALS = {
    "hour": "1 hour",
    "day": "1 day",
    "week": "7 days",
    "month": "30 days",
}


@router.get("/analytics/usage", response_model=None, tags=["analytics"])
async def analytics_usage_endpoint(
    period: str = Query("day", pattern="^(hour|day|week|month)$"),
    model: Optional[str] = None,
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
) -> Dict[str, Any]:
    interval = _PERIOD_INTERVALS.get(period, "1 day")
    data = await usage_analytics(db, interval, model)
    return ok(data)


@router.get("/analytics/models", response_model=None, tags=["analytics"])
async def analytics_models_endpoint(
    client: httpx.AsyncClient = Depends(get_http_client),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
) -> Dict[str, Any]:
    data = await model_analytics(db, client)
    return ok(data)


@router.get("/analytics/rag", response_model=None, tags=["analytics"])
async def analytics_rag_endpoint(
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
) -> Dict[str, Any]:
    data = await rag_analytics(db)
    return ok(data)


@router.get("/analytics/services/history", response_model=None, tags=["analytics"])
async def analytics_services_history_endpoint(
    service: Optional[str] = None,
    hours: int = Query(24, ge=1, le=168),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
) -> Dict[str, Any]:
    data = await services_history(db, service, hours)
    return ok(data)
