"""Analytics routes."""

import hashlib
from typing import Any, Dict, Optional

import asyncpg
import httpx
from fastapi import APIRouter, Depends, Query

from api.dependencies import get_db_optional, get_http_client, get_redis
from api.repositories.redis_cache import RedisCacheRepository
from api.schemas.envelope import ok
from api.services.analytics import (
    model_analytics,
    rag_analytics,
    services_history,
    usage_analytics,
)
from api.services.cache import get_cached, set_cached

# Auth is enforced at the v1_router level in app.py — no per-router dependency needed.
router = APIRouter()

_PERIOD_INTERVALS = {
    "hour": "1 hour",
    "day": "1 day",
    "week": "7 days",
    "month": "30 days",
}

_CACHE_PREFIX = "manic:cache:analytics"


def _params_hash(*parts: Any) -> str:
    """Stable short hash of cache-key parameters."""
    raw = ":".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


@router.get("/analytics/usage", response_model=None, tags=["analytics"])
async def analytics_usage_endpoint(
    period: str = Query("day", pattern="^(hour|day|week|month)$"),
    model: Optional[str] = Query(None, max_length=200),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
    redis: Optional[RedisCacheRepository] = Depends(get_redis),
) -> Dict[str, Any]:
    cache_key = f"{_CACHE_PREFIX}:usage:{_params_hash(period, model)}"
    cached = await get_cached(redis, cache_key)
    if cached is not None:
        return ok(cached)

    interval = _PERIOD_INTERVALS.get(period, "1 day")
    data = await usage_analytics(db, interval, model)
    await set_cached(redis, cache_key, data, ttl=60)
    return ok(data)


@router.get("/analytics/models", response_model=None, tags=["analytics"])
async def analytics_models_endpoint(
    client: httpx.AsyncClient = Depends(get_http_client),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
    redis: Optional[RedisCacheRepository] = Depends(get_redis),
) -> Dict[str, Any]:
    cache_key = f"{_CACHE_PREFIX}:models:{_params_hash()}"
    cached = await get_cached(redis, cache_key)
    if cached is not None:
        return ok(cached)

    data = await model_analytics(db, client)
    await set_cached(redis, cache_key, data, ttl=60)
    return ok(data)


@router.get("/analytics/rag", response_model=None, tags=["analytics"])
async def analytics_rag_endpoint(
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
    redis: Optional[RedisCacheRepository] = Depends(get_redis),
) -> Dict[str, Any]:
    cache_key = f"{_CACHE_PREFIX}:rag:{_params_hash()}"
    cached = await get_cached(redis, cache_key)
    if cached is not None:
        return ok(cached)

    data = await rag_analytics(db)
    await set_cached(redis, cache_key, data, ttl=60)
    return ok(data)


@router.get("/analytics/services/history", response_model=None, tags=["analytics"])
async def analytics_services_history_endpoint(
    service: Optional[str] = Query(None, max_length=100, pattern=r"^[a-zA-Z0-9_\-]+$"),
    hours: int = Query(24, ge=1, le=168),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
    redis: Optional[RedisCacheRepository] = Depends(get_redis),
) -> Dict[str, Any]:
    cache_key = f"{_CACHE_PREFIX}:services_history:{_params_hash(service, hours)}"
    cached = await get_cached(redis, cache_key)
    if cached is not None:
        return ok(cached)

    data = await services_history(db, service, hours)
    await set_cached(redis, cache_key, data, ttl=30)
    return ok(data)
