"""Admin router — user management and system stats.

All endpoints require a valid API key that belongs to an admin user.
The ``require_admin`` dependency enforces this check; the standard
``require_api_key`` dep (mounted at router level in app.py) runs first
to reject completely missing / invalid keys before we hit the DB.
"""

from typing import Any, Dict, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field

from api.dependencies import get_db
from api.schemas.envelope import ok
from api.services import admin as admin_svc
from api.services.user_auth import authenticate_by_api_key, create_user

router = APIRouter()


# ---------------------------------------------------------------------------
# Admin-guard dependency
# ---------------------------------------------------------------------------


async def require_admin(
    request: Request,
    db: asyncpg.Pool = Depends(get_db),
) -> Dict[str, Any]:
    """Verify the caller is an active admin user.

    Reads ``X-API-Key`` from request headers, authenticates against the
    users table, and rejects non-admin callers with 403.

    Returns:
        The authenticated user mapping (id, email, username, is_admin, …).
    """
    key: Optional[str] = request.headers.get("X-API-Key")
    if not key:
        raise HTTPException(status_code=401, detail="Missing API key")

    user = await authenticate_by_api_key(db, key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    username: Optional[str] = Field(default=None, max_length=64)
    is_admin: bool = False


class UpdateUserRequest(BaseModel):
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    rate_limit_override: Optional[int] = Field(default=None, ge=1, le=10_000)
    username: Optional[str] = Field(default=None, max_length=64)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/admin/users", response_model=None, tags=["admin"])
async def list_users(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: asyncpg.Pool = Depends(get_db),
    _admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """List all users with pagination.

    Returns a paginated array of users with masked API keys.
    """
    data = await admin_svc.list_users(db, limit=limit, offset=offset)
    return ok(data, meta={"limit": limit, "offset": offset, "total": data["total"]})


@router.get("/admin/users/{user_id}", response_model=None, tags=["admin"])
async def get_user(
    user_id: str,
    db: asyncpg.Pool = Depends(get_db),
    _admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Fetch a single user by UUID."""
    user = await admin_svc.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return ok(user)


@router.post("/admin/users", response_model=None, tags=["admin"])
async def create_user_endpoint(
    body: CreateUserRequest,
    db: asyncpg.Pool = Depends(get_db),
    _admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Create a new user account.

    Generates a unique API key automatically. If ``is_admin`` is True
    the account will have admin privileges immediately.
    """
    try:
        user = await create_user(
            db,
            email=body.email,
            password=body.password,
            username=body.username,
        )
    except asyncpg.UniqueViolationError as exc:
        raise HTTPException(
            status_code=409,
            detail="A user with that email or username already exists",
        ) from exc

    # If admin flag was requested, apply it now
    if body.is_admin:
        user = await admin_svc.update_user(db, user["id"], is_admin=True) or user

    return ok(user)


@router.patch("/admin/users/{user_id}", response_model=None, tags=["admin"])
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    db: asyncpg.Pool = Depends(get_db),
    _admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Partially update a user (toggle active/admin, set rate limit, rename).

    Only fields present in the request body are modified.
    """
    user = await admin_svc.update_user(
        db,
        user_id,
        is_active=body.is_active,
        is_admin=body.is_admin,
        rate_limit_override=body.rate_limit_override,
        username=body.username,
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return ok(user)


@router.delete("/admin/users/{user_id}", response_model=None, tags=["admin"])
async def deactivate_user(
    user_id: str,
    db: asyncpg.Pool = Depends(get_db),
    _admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Soft-delete a user by setting is_active = FALSE.

    The account and all its data are retained; the user simply cannot
    authenticate until re-activated via PATCH.
    """
    deactivated = await admin_svc.deactivate_user(db, user_id)
    if not deactivated:
        raise HTTPException(status_code=404, detail="User not found")
    return ok({"user_id": user_id, "deactivated": True})


@router.get("/admin/stats", response_model=None, tags=["admin"])
async def system_stats(
    db: asyncpg.Pool = Depends(get_db),
    _admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Return system-wide aggregate statistics.

    Covers total/active users, admin count, chats, searches, and feedback.
    """
    stats = await admin_svc.get_system_stats(db)
    return ok(stats)
