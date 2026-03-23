"""Authentication routes — login and token issuance.

Mounted at the root (not under /v1/) so clients can obtain an API key
without needing one first. No ``require_api_key`` dependency is applied
here; rate limiting and guardrails middleware still run for every request.
"""

import logging
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import asyncpg
import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr

from api.config import settings
from api.dependencies import get_db, get_redis
from api.middleware.rate_limit import limiter
from api.schemas.envelope import ok
from api.services.user_auth import authenticate_by_email, create_user

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


class MFALoginResponse(BaseModel):
    """Returned when a user has MFA enabled — client must complete validation."""

    mfa_required: bool
    mfa_token: str
    user_id: str
    email: str


@router.post("/auth/login", response_model=None, summary="Obtain an API key via email + password")
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    db: asyncpg.Pool = Depends(get_db),
    redis=Depends(get_redis),
) -> Dict[str, Any]:
    """Authenticate a user by email and password.

    Returns the user's persistent API key on success. When MFA is enabled the
    response will instead contain ``mfa_required: true`` and an ``mfa_token``
    that the client must exchange via ``POST /auth/mfa/validate``.

    Raises:
        HTTPException 401: If the credentials are invalid or the account
            is inactive.
    """
    user = await authenticate_by_email(db, body.email, body.password, redis=redis)
    if not user:
        # Constant-time path: always the same error regardless of whether
        # the email exists, to avoid user-enumeration.
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.get("mfa_required"):
        logger.info("MFA required for user %s", user["user_id"])
        return ok(MFALoginResponse(**user).model_dump())

    logger.info("Successful login for user %s", user["id"])
    return ok(
        LoginResponse(
            api_key=user["api_key"],
            user_id=user["id"],
            email=user["email"],
        ).model_dump()
    )


# ---------------------------------------------------------------------------
# MFA endpoints
# ---------------------------------------------------------------------------


class MFASetupResponse(BaseModel):
    """TOTP provisioning data returned on setup."""

    totp_secret: str
    provisioning_uri: str


class MFACodeRequest(BaseModel):
    """A TOTP code submitted by the client."""

    code: str


class MFAValidateRequest(BaseModel):
    """MFA token + TOTP code to complete a login when MFA is enabled."""

    mfa_token: str
    code: str


@router.post(
    "/auth/mfa/setup",
    response_model=None,
    summary="Generate a TOTP secret and provisioning URI",
)
@limiter.limit("5/minute")
async def mfa_setup(
    request: Request,
    db: asyncpg.Pool = Depends(get_db),
) -> Dict[str, Any]:
    """Generate a new TOTP secret for the authenticated user.

    The returned ``provisioning_uri`` can be rendered as a QR code by the
    client so the user can enrol their authenticator app. The secret is stored
    on the user record but MFA is not activated until the user verifies a code
    via ``POST /auth/mfa/verify``.

    Raises:
        HTTPException 401: When no authenticated user is found on the request.
    """
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    totp_secret = pyotp.random_base32()
    provisioning_uri = pyotp.totp.TOTP(totp_secret).provisioning_uri(
        name=user["email"],
        issuer_name="Manic AI",
    )

    async with db.acquire() as conn:
        await conn.execute(
            "UPDATE public.users SET totp_secret = $1 WHERE id = $2",
            totp_secret,
            user["id"],
        )

    logger.info("MFA setup initiated for user %s", user["id"])
    return ok(MFASetupResponse(totp_secret=totp_secret, provisioning_uri=provisioning_uri).model_dump())


@router.post(
    "/auth/mfa/verify",
    response_model=None,
    summary="Verify a TOTP code and activate MFA",
)
@limiter.limit("5/minute")
async def mfa_verify(
    request: Request,
    body: MFACodeRequest,
    db: asyncpg.Pool = Depends(get_db),
) -> Dict[str, Any]:
    """Verify a TOTP code and, on success, set ``mfa_enabled = true``.

    The user must have previously called ``POST /auth/mfa/setup`` so a secret
    exists on their record. A valid code confirms the authenticator app is
    correctly enrolled.

    Raises:
        HTTPException 401: When not authenticated.
        HTTPException 400: When no TOTP secret is found or the code is invalid.
    """
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT totp_secret FROM public.users WHERE id = $1",
            user["id"],
        )

    if not row or not row["totp_secret"]:
        raise HTTPException(status_code=400, detail="No TOTP secret found. Call /auth/mfa/setup first.")

    if not pyotp.TOTP(row["totp_secret"]).verify(body.code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    async with db.acquire() as conn:
        await conn.execute(
            "UPDATE public.users SET mfa_enabled = TRUE WHERE id = $1",
            user["id"],
        )

    logger.info("MFA activated for user %s", user["id"])
    return ok({"message": "MFA enabled successfully"})


@router.post(
    "/auth/mfa/validate",
    response_model=None,
    summary="Exchange an MFA token + TOTP code for an API key",
)
@limiter.limit("10/minute")
async def mfa_validate(
    request: Request,
    body: MFAValidateRequest,
    db: asyncpg.Pool = Depends(get_db),
    redis=Depends(get_redis),
) -> Dict[str, Any]:
    """Complete the login flow when MFA is required.

    After ``POST /auth/login`` returns ``mfa_required: true``, the client
    supplies the ``mfa_token`` from that response and the current TOTP code.
    On success the user's API key is returned.

    Raises:
        HTTPException 401: When the MFA token is missing, expired, or the
            TOTP code is invalid.
    """
    if redis is None:
        raise HTTPException(status_code=503, detail="MFA validation requires Redis")

    user_id: Optional[str] = await redis.get(f"mfa_token:{body.mfa_token}")
    if not user_id:
        raise HTTPException(status_code=401, detail="MFA token is invalid or has expired")

    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id::text, email, api_key, totp_secret FROM public.users WHERE id = $1 AND is_active = TRUE",
            user_id,
        )

    if not row or not row["totp_secret"]:
        raise HTTPException(status_code=401, detail="User not found or MFA not configured")

    if not pyotp.TOTP(row["totp_secret"]).verify(body.code):
        raise HTTPException(status_code=401, detail="Invalid TOTP code")

    # Consume the token so it cannot be reused.
    await redis.delete_pattern(f"mfa_token:{body.mfa_token}")

    logger.info("MFA validated — issuing API key for user %s", row["id"])
    return ok(
        LoginResponse(
            api_key=row["api_key"],
            user_id=row["id"],
            email=row["email"],
        ).model_dump()
    )


class RegisterRequest(BaseModel):
    """Self-service account creation payload."""

    email: EmailStr
    password: str
    display_name: Optional[str] = None


@router.post(
    "/auth/register",
    response_model=None,
    status_code=201,
    summary="Create a new user account (multi_user mode only)",
)
@limiter.limit("3/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    db: asyncpg.Pool = Depends(get_db),
) -> Dict[str, Any]:
    """Register a new user account and return the issued API key.

    Only available when ``AUTH_MODE=multi_user``. Returns HTTP 404 in
    single-user mode so the endpoint is not discoverable in that configuration.

    Rate limited to 3 requests per minute per IP to prevent abuse.

    Returns:
        HTTP 201 with ``{ "message": "Account created", "api_key": "..." }``

    Raises:
        HTTPException 404: When AUTH_MODE is not multi_user.
        HTTPException 409: When the email address is already registered.
        HTTPException 400: When the email address format is invalid.
    """
    if settings.AUTH_MODE != "multi_user":
        raise HTTPException(status_code=404, detail="Not found")

    try:
        user = await create_user(
            db,
            email=str(body.email),
            password=body.password,
            username=body.display_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        # asyncpg raises UniqueViolationError for duplicate email/username.
        # Import lazily to avoid a hard dependency on asyncpg internals.
        import asyncpg as _asyncpg

        if isinstance(exc, _asyncpg.UniqueViolationError):
            raise HTTPException(
                status_code=409,
                detail="An account with this email address already exists.",
            )
        logger.exception("Unexpected error during user registration")
        raise HTTPException(status_code=500, detail="Registration failed")

    logger.info("New user registered: %s (id=%s)", user["email"], user["id"])
    return ok({"message": "Account created", "api_key": user["api_key"]})


@router.post("/auth/rotate-key", response_model=None, summary="Rotate the current API key")
@limiter.limit("3/minute")
async def rotate_key(
    request: Request,
    db: asyncpg.Pool = Depends(get_db),
) -> Dict[str, Any]:
    """Generate a new API key, invalidating the old one.

    The caller must supply the current API key via ``X-API-Key``. On success
    the response contains the new key and its expiry timestamp. The old key
    is immediately invalidated.

    Raises:
        HTTPException 401: When no authenticated user is found on the request.
    """
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    new_key = f"manic_{secrets.token_urlsafe(32)}"
    new_expires = datetime.utcnow() + timedelta(days=90)
    async with db.acquire() as conn:
        await conn.execute(
            "UPDATE public.users SET api_key = $1, key_expires_at = $2 WHERE id = $3",
            new_key,
            new_expires,
            user["id"],
        )
    logger.info("API key rotated for user %s", user["id"])
    return ok({"api_key": new_key, "expires_at": new_expires.isoformat()})


@router.post("/auth/logout", response_model=None, summary="Invalidate the current API key")
async def logout(
    request: Request,
    db: asyncpg.Pool = Depends(get_db),
) -> Dict[str, Any]:
    """Invalidate the current API key by replacing it with a new random key.

    After calling this endpoint the caller's ``X-API-Key`` will no longer be
    accepted. The replacement key is not returned to the client.

    Raises:
        HTTPException 401: When no authenticated user is found on the request.
    """
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    new_key = f"manic_{secrets.token_urlsafe(32)}"
    async with db.acquire() as conn:
        await conn.execute(
            "UPDATE public.users SET api_key = $1 WHERE id = $2",
            new_key,
            user["id"],
        )
    logger.info("User %s logged out — API key invalidated", user["id"])
    return ok({"message": "Logged out. Previous API key is now invalid."})
