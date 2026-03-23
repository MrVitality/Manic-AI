"""Per-IP rate limiting via slowapi."""

import logging

from slowapi import Limiter
from slowapi.util import get_remote_address

from api.config import settings

logger = logging.getLogger(__name__)

try:
    limiter = Limiter(key_func=get_remote_address, storage_uri=settings.REDIS_URL)
    logger.info("Rate limiter using Redis storage: %s", settings.REDIS_URL)
except Exception as _exc:
    logger.warning(
        "Rate limiter could not connect to Redis (%s); falling back to in-memory storage. "
        "Rate limits will NOT be shared across multiple API instances.",
        _exc,
    )
    limiter = Limiter(key_func=get_remote_address)
