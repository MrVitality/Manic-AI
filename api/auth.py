import hmac
import logging
import os

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from api.config import settings

logger = logging.getLogger(__name__)

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

_secret_key: str | None = settings.API_SECRET_KEY or None

# ---------------------------------------------------------------------------
# Startup check: require explicit opt-in when API_SECRET_KEY is not set
# ---------------------------------------------------------------------------
# If API_SECRET_KEY is absent the API would silently accept all requests.
# This is only permissible in local-dev mode, signalled by the operator
# setting ALLOW_UNAUTHENTICATED=true explicitly.  Any other deployment
# (staging, production, CI with a real DB) must configure the key.

_allow_unauthenticated: bool = (
    os.environ.get("ALLOW_UNAUTHENTICATED", "").strip().lower() == "true"
)

if not _secret_key:
    if _allow_unauthenticated:
        logger.warning(
            "API_SECRET_KEY is not set and ALLOW_UNAUTHENTICATED=true — "
            "all endpoints are running WITHOUT authentication. "
            "This is only safe for local development."
        )
    else:
        raise RuntimeError(
            "API_SECRET_KEY environment variable is not set. "
            "The API refuses to start without authentication configured. "
            "For local development only, set ALLOW_UNAUTHENTICATED=true to "
            "explicitly opt in to unauthenticated mode."
        )


async def require_api_key(key: str | None = Security(_API_KEY_HEADER)) -> None:
    """Dependency that enforces API key authentication.

    When API_SECRET_KEY is not configured AND ALLOW_UNAUTHENTICATED=true
    (local dev), authentication is skipped with a startup warning.
    When API_SECRET_KEY IS configured, every request must supply a matching
    'X-API-Key' header or receive a 401.
    """
    if not _secret_key:
        # Auth disabled -- explicit local-dev opt-in, warning logged at import.
        return

    if not key or not hmac.compare_digest(key, _secret_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
