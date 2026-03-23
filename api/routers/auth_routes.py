"""Authentication routes — login and token issuance.

Mounted at the root (not under /v1/) so clients can obtain an API key
without needing one first. No ``require_api_key`` dependency is applied
here; rate limiting and guardrails middleware still run for every request.
"""

import logging
from typing import Any, Dict

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr

from api.dependencies import get_db
from api.middleware.rate_limit import limiter
from api.schemas.envelope import ok
from api.services.user_auth import authenticate_by_email

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    """Credentials submitted by the client."""

    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Successful login payload returned inside the standard envelope."""

    api_key: str
    user_id: str
    email: str


@router.post("/auth/login", response_model=None, summary="Obtain an API key via email + password")
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    db: asyncpg.Pool = Depends(get_db),
) -> Dict[str, Any]:
    """Authenticate a user by email and password.

    Returns the user's persistent API key on success. The API key should
    be supplied as the ``X-API-Key`` header on all subsequent requests.

    Raises:
        HTTPException 401: If the credentials are invalid or the account
            is inactive.
    """
    user = await authenticate_by_email(db, body.email, body.password)
    if not user:
        # Constant-time path: always the same error regardless of whether
        # the email exists, to avoid user-enumeration.
        raise HTTPException(status_code=401, detail="Invalid email or password")

    logger.info("Successful login for user %s", user["id"])
    return ok(
        LoginResponse(
            api_key=user["api_key"],
            user_id=user["id"],
            email=user["email"],
        ).model_dump()
    )
