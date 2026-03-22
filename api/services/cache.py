"""Simple cache helpers for Redis-backed response caching."""

import json
import logging
from typing import Any, Optional

from api.repositories.redis_cache import RedisCacheRepository

logger = logging.getLogger(__name__)


async def get_cached(redis: Optional[RedisCacheRepository], key: str) -> Optional[Any]:
    """Return a deserialized cached value, or None on miss or error."""
    if not redis:
        return None
    raw = await redis.get(key)
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            logger.warning("Cache deserialisation failed for key %s", key)
    return None


async def set_cached(
    redis: Optional[RedisCacheRepository],
    key: str,
    data: Any,
    ttl: int = 60,
) -> None:
    """Serialise *data* to JSON and store it with the given TTL (seconds)."""
    if not redis:
        return
    try:
        await redis.setex(key, ttl, json.dumps(data, default=str))
    except Exception:
        logger.warning("Cache serialisation failed for key %s", key)
