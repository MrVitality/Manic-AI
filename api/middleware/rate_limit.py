"""Per-user (or per-IP fallback) rate limiting via slowapi."""

import logging

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from api.config import settings

logger = logging.getLogger(__name__)


def _user_or_ip_key(request: Request) -> str:
    """Return the authenticated user's ID when available, else the remote IP.

    Using the user ID as the rate-limit key ensures that authenticated clients
    are tracked consistently regardless of IP (e.g. behind a proxy or VPN),
    and that a single IP cannot exhaust limits across multiple accounts.

    TODO: honour per-user ``rate_limit_override`` — when the user record
    carries a non-null override value the per-user bucket should use that
    limit instead of the global default.
    """
    user = getattr(request.state, "user", None)
    if user and user.get("id"):
        return f"user:{user['id']}"
    return get_remote_address(request)


try:
    limiter = Limiter(key_func=_user_or_ip_key, storage_uri=settings.REDIS_URL)
    logger.info("Rate limiter using Redis storage: %s", settings.REDIS_URL)
except Exception as _exc:
    logger.warning(
        "Rate limiter could not connect to Redis (%s); falling back to in-memory storage. "
        "Rate limits will NOT be shared across multiple API instances.",
        _exc,
    )
    limiter = Limiter(key_func=_user_or_ip_key)
