"""Embedding generation with optional Redis cache."""

import json
import logging
from hashlib import sha256
from typing import List, Optional

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_redis = None


def _set_redis(client):
    """Replace the module-level Redis reference without ``global``."""
    import api.services.embedding as _mod
    _mod._redis = client


async def init_redis(*, app=None):
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(settings.REDIS_URL)
        await client.ping()
        _set_redis(client)
        logger.info("Redis embedding cache enabled")
        if app is not None:
            from api.repositories.redis_cache import RedisCacheRepository
            app.state.redis_cache = RedisCacheRepository(client)
    except Exception as e:
        logger.warning("Redis unavailable, embedding cache disabled: %s", e)
        _set_redis(None)


async def generate_embedding(
    text: str,
    model: str = None,
    client: Optional[httpx.AsyncClient] = None,
) -> List[float]:
    model = model or settings.EMBEDDING_MODEL
    cache_key = f"manic:emb:{sha256(f'{model}:{text}'.encode()).hexdigest()}"

    if _redis:
        try:
            cached = await _redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning("Redis get failed: %s", e)

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=60.0)
    try:
        response = await client.post(
            f"{settings.OLLAMA_URL}/api/embeddings",
            json={"model": model, "prompt": text},
        )
        response.raise_for_status()
        embedding = response.json()["embedding"]
    finally:
        if own_client:
            await client.aclose()

    if _redis:
        try:
            await _redis.setex(cache_key, 3600, json.dumps(embedding))
        except Exception as e:
            logger.warning("Redis set failed: %s", e)

    return embedding
