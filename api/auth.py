import hmac
import logging
import os
from typing import Optional

from fastapi import HTTPException, Request, Security, status
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


async def require_api_key(
    request: Request,
    key: str | None = Security(_API_KEY_HEADER),
) -> None:
    """Dependency that enforces API key authentication.

    Single-user mode (AUTH_MODE=single, default):
        Every request must supply the shared API_SECRET_KEY in the
        X-API-Key header, or receive a 401.  request.state.user is set
        to None so downstream code can detect single-key mode.

    Multi-user mode (AUTH_MODE=multi_user):
        The X-API-Key value is looked up in the users table via
        authenticate_by_api_key().  On success, the resolved user dict
        (id, email, is_admin, is_active, ...) is stored on
        request.state.user.  Invalid or inactive keys yield 401.

    When API_SECRET_KEY is not configured AND ALLOW_UNAUTHENTICATED=true
    (local dev), authentication is skipped entirely.
    """
    if not _secret_key:
        # Auth disabled -- explicit local-dev opt-in, warning logged at import.
        request.state.user = None
        return

    if settings.AUTH_MODE == "multi_user":
        # Per-user API key authentication.
        if not key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-API-Key header.",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        pool = getattr(request.app.state, "db_pool", None)
        if pool is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not connected.",
            )

        from api.services.user_auth import authenticate_by_api_key

        user = await authenticate_by_api_key(pool, key)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or inactive API key.",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        # Ensure is_active is present; authenticate_by_api_key only returns
        # rows where is_active = TRUE, so we can safely set it here.
        user.setdefault("is_active", True)
        request.state.user = user
        return

    # Single-key mode: compare against shared secret.
    request.state.user = None
    if not key or not hmac.compare_digest(key, _secret_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )


def get_current_user_id(request: Request) -> Optional[str]:
    """Return the authenticated user's id, or None in single-key mode.

    In multi_user mode the user dict is placed on request.state.user by
    require_api_key.  In single-key (or unauthenticated dev) mode,
    request.state.user is None and this returns None so callers can fall
    back to client-supplied values.
    """
    user = getattr(request.state, "user", None)
    if user and isinstance(user, dict):
        uid = user.get("id", "")
        return str(uid) if uid else None
    return None
