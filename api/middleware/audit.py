"""Audit middleware — fire-and-forget API key usage logging."""

import asyncio
import logging
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

import asyncpg

logger = logging.getLogger(__name__)


async def _log_usage(request: Request, user: dict) -> None:
    """Insert a row into api_key_usage_log for the authenticated request."""
    db: Optional[asyncpg.Pool] = getattr(request.app.state, "db_pool", None)
    if db is None:
        return

    api_key_prefix = user.get("api_key_prefix") or None
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    endpoint = request.url.path
    method = request.method

    try:
        async with db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.api_key_usage_log
                    (user_id, api_key_prefix, endpoint, method, ip_address, user_agent)
                VALUES ($1, $2, $3, $4, $5::inet, $6)
                """,
                user["id"],
                api_key_prefix,
                endpoint,
                method,
                ip_address,
                user_agent,
            )
    except Exception as exc:
        # Audit failure must never break the main request path.
        logger.warning("Audit log insert failed: %s", exc)


class AuditMiddleware(BaseHTTPMiddleware):
    """Logs API key usage for authenticated requests.

    Inserts are fire-and-forget via ``asyncio.create_task`` so the main
    response is never blocked or delayed by the audit write.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        user = getattr(request.state, "user", None)
        if user:
            asyncio.create_task(_log_usage(request, user))
        return response
