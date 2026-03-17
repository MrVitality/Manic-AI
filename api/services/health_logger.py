"""Background health logger — logs service status to public.service_health_log every 60s."""
import asyncio
import logging
from typing import Optional

from api.services.rag import check_service
from api.config import OLLAMA_URL, QDRANT_URL, SEARXNG_URL, LANGFUSE_HOST
from api.database import get_db_optional

logger = logging.getLogger(__name__)


async def log_services_once(db, client) -> None:
    """Check all services and insert one row per service into service_health_log."""
    services = {
        "ollama": f"{OLLAMA_URL}/api/tags",
        "qdrant": f"{QDRANT_URL}/collections",
        "searxng": f"{SEARXNG_URL}/healthz",
        "langfuse": f"{LANGFUSE_HOST}",
    }

    results = await asyncio.gather(
        *[check_service(url, client) for url in services.values()],
        return_exceptions=True,
    )

    async with db.acquire() as conn:
        for (name, _), result in zip(services.items(), results):
            if isinstance(result, BaseException):
                continue
            await conn.execute(
                """INSERT INTO public.service_health_log (service_name, status, latency_ms)
                   VALUES ($1, $2, $3)""",
                name,
                result.get("status", "offline"),
                result.get("latency_ms"),
            )


async def health_log_loop() -> None:
    """Run forever — log service health every 60 seconds."""
    while True:
        await asyncio.sleep(60)
        try:
            db = get_db_optional()
            if not db:
                continue
            # Import here to avoid circular imports at module load time
            from api.http_client import get_client
            client = get_client()
            await log_services_once(db, client)
        except Exception as e:
            logger.error("Health log error: %s", e)
