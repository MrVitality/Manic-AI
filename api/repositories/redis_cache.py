"""Redis cache repository."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RedisCacheRepository:
    """Wraps Redis operations behind the CacheStore protocol."""

    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    async def get(self, key: str) -> Optional[str]:
        try:
            return await self._redis.get(key)
        except Exception as e:
            logger.warning("Redis get failed: %s", e)
            return None

    async def setex(self, key: str, ttl: int, value: str) -> None:
        try:
            await self._redis.setex(key, ttl, value)
        except Exception as e:
            logger.warning("Redis set failed: %s", e)

    async def delete_pattern(self, pattern: str) -> int:
        try:
            keys = await self._redis.keys(pattern)
            if keys:
                return await self._redis.delete(*keys)
            return 0
        except Exception as e:
            logger.warning("Redis delete_pattern failed: %s", e)
            return 0

    async def close(self) -> None:
        try:
            await self._redis.aclose()
        except Exception:
            pass
