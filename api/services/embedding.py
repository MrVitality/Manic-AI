import json
from hashlib import sha256
from typing import List, Optional
import httpx

from api.config import OLLAMA_URL, EMBEDDING_MODEL, REDIS_URL

_redis = None


async def init_redis():
    global _redis
    try:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(REDIS_URL)
        # Test connection
        await _redis.ping()
        print("Redis embedding cache enabled")
    except Exception as e:
        print(f"[WARN] Redis unavailable, embedding cache disabled: {e}")
        _redis = None


async def generate_embedding(
    text: str,
    model: str = None,
    client: Optional[httpx.AsyncClient] = None,
) -> List[float]:
    model = model or EMBEDDING_MODEL
    cache_key = f"manic:emb:{sha256(f'{model}:{text}'.encode()).hexdigest()}"

    if _redis:
        try:
            cached = await _redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            print(f"[WARN] Redis get failed: {e}")

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=60.0)
    try:
        response = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
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
            print(f"[WARN] Redis set failed: {e}")

    return embedding
