import logging

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from api.config import settings

logger = logging.getLogger(__name__)

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

_secret_key: str | None = settings.API_SECRET_KEY or None

if not _secret_key:
    logger.warning(
        "API_SECRET_KEY is not set -- all endpoints are UNAUTHENTICATED. "
        "Set this environment variable before deploying to production."
    )


async def require_api_key(key: str | None = Security(_API_KEY_HEADER)) -> None:
    """Dependency that enforces API key authentication.

    When API_SECRET_KEY is not configured (local dev), authentication is
    skipped with a startup warning.  When it IS configured, every request
    must supply a matching 'X-API-Key' header or receive a 401.
    """
    if not _secret_key:
        # Auth disabled -- local-dev mode, warning already logged at import.
        return

    if not key or key != _secret_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
