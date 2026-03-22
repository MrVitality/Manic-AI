"""Tests for the admin router — user management and system stats."""

from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ADMIN_KEY = "manic_adminkey123"
NON_ADMIN_KEY = "manic_userkey456"

_ADMIN_USER = {
    "id": "aaaaaaaa-0000-0000-0000-000000000001",
    "email": "admin@example.com",
    "username": "admin",
    "is_admin": True,
    "rate_limit_override": None,
}

_REGULAR_USER = {
    "id": "bbbbbbbb-0000-0000-0000-000000000002",
    "email": "user@example.com",
    "username": "user",
    "is_admin": False,
    "rate_limit_override": None,
}

_USER_ROW = {
    "id": "aaaaaaaa-0000-0000-0000-000000000001",
    "email": "admin@example.com",
    "username": "admin",
    "is_active": True,
    "is_admin": True,
    "api_key_masked": "manic_adminke...",
    "rate_limit_override": None,
    "created_at": "2025-01-01T00:00:00",
    "updated_at": "2025-01-01T00:00:00",
}


async def _auth_side_effect(db, key: str):
    """Return different users based on which API key is supplied."""
    if key == ADMIN_KEY:
        return _ADMIN_USER
    if key == NON_ADMIN_KEY:
        return _REGULAR_USER
    return None


# ---------------------------------------------------------------------------
# /admin/users  — list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_users_admin(client):
    with (
        patch(
            "api.routers.admin.authenticate_by_api_key",
            new=AsyncMock(side_effect=_auth_side_effect),
        ),
        patch(
            "api.services.admin.list_users",
            new=AsyncMock(
                return_value={
                    "users": [_USER_ROW],
                    "total": 1,
                    "limit": 50,
                    "offset": 0,
                }
            ),
        ),
    ):
        resp = await client.get(
            "/v1/admin/users",
            headers={"X-API-Key": ADMIN_KEY},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["total"] == 1
    assert len(body["data"]["users"]) == 1


@pytest.mark.asyncio
async def test_list_users_non_admin_gets_403(client):
    with patch(
        "api.routers.admin.authenticate_by_api_key",
        new=AsyncMock(side_effect=_auth_side_effect),
    ):
        resp = await client.get(
            "/v1/admin/users",
            headers={"X-API-Key": NON_ADMIN_KEY},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_users_no_key_gets_401(client):
    resp = await client.get("/v1/admin/users")
    # Either 401 from our dep or 403 from require_api_key middleware
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# /admin/users/{user_id}  — get single
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_user_found(client):
    with (
        patch(
            "api.routers.admin.authenticate_by_api_key",
            new=AsyncMock(side_effect=_auth_side_effect),
        ),
        patch(
            "api.services.admin.get_user",
            new=AsyncMock(return_value=_USER_ROW),
        ),
    ):
        resp = await client.get(
            f"/v1/admin/users/{_USER_ROW['id']}",
            headers={"X-API-Key": ADMIN_KEY},
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == "admin@example.com"


@pytest.mark.asyncio
async def test_get_user_not_found(client):
    with (
        patch(
            "api.routers.admin.authenticate_by_api_key",
            new=AsyncMock(side_effect=_auth_side_effect),
        ),
        patch(
            "api.services.admin.get_user",
            new=AsyncMock(return_value=None),
        ),
    ):
        resp = await client.get(
            "/v1/admin/users/nonexistent-id",
            headers={"X-API-Key": ADMIN_KEY},
        )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /admin/users  — create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_user(client):
    new_user = {
        "id": "cccccccc-0000-0000-0000-000000000003",
        "email": "new@example.com",
        "username": "newuser",
        "api_key": "manic_newkeyxyz",
        "created_at": "2025-06-01T00:00:00",
    }
    with (
        patch(
            "api.routers.admin.authenticate_by_api_key",
            new=AsyncMock(side_effect=_auth_side_effect),
        ),
        patch(
            "api.routers.admin.create_user",
            new=AsyncMock(return_value=new_user),
        ),
    ):
        resp = await client.post(
            "/v1/admin/users",
            json={
                "email": "new@example.com",
                "password": "securepass1",
                "username": "newuser",
                "is_admin": False,
            },
            headers={"X-API-Key": ADMIN_KEY},
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == "new@example.com"


@pytest.mark.asyncio
async def test_create_user_conflict(client):
    import asyncpg

    with (
        patch(
            "api.routers.admin.authenticate_by_api_key",
            new=AsyncMock(side_effect=_auth_side_effect),
        ),
        patch(
            "api.routers.admin.create_user",
            new=AsyncMock(
                side_effect=asyncpg.UniqueViolationError(
                    "duplicate key value violates unique constraint"
                )
            ),
        ),
    ):
        resp = await client.post(
            "/v1/admin/users",
            json={
                "email": "admin@example.com",
                "password": "securepass1",
            },
            headers={"X-API-Key": ADMIN_KEY},
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_user_short_password(client):
    with patch(
        "api.routers.admin.authenticate_by_api_key",
        new=AsyncMock(side_effect=_auth_side_effect),
    ):
        resp = await client.post(
            "/v1/admin/users",
            json={"email": "x@y.com", "password": "short"},
            headers={"X-API-Key": ADMIN_KEY},
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /admin/users/{user_id}  — update (PATCH)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_user(client):
    updated = {**_USER_ROW, "is_active": False}
    with (
        patch(
            "api.routers.admin.authenticate_by_api_key",
            new=AsyncMock(side_effect=_auth_side_effect),
        ),
        patch(
            "api.services.admin.update_user",
            new=AsyncMock(return_value=updated),
        ),
    ):
        resp = await client.patch(
            f"/v1/admin/users/{_USER_ROW['id']}",
            json={"is_active": False},
            headers={"X-API-Key": ADMIN_KEY},
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is False


@pytest.mark.asyncio
async def test_update_user_not_found(client):
    with (
        patch(
            "api.routers.admin.authenticate_by_api_key",
            new=AsyncMock(side_effect=_auth_side_effect),
        ),
        patch(
            "api.services.admin.update_user",
            new=AsyncMock(return_value=None),
        ),
    ):
        resp = await client.patch(
            "/v1/admin/users/nonexistent",
            json={"is_active": True},
            headers={"X-API-Key": ADMIN_KEY},
        )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /admin/users/{user_id}  — deactivate (DELETE)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deactivate_user(client):
    with (
        patch(
            "api.routers.admin.authenticate_by_api_key",
            new=AsyncMock(side_effect=_auth_side_effect),
        ),
        patch(
            "api.services.admin.deactivate_user",
            new=AsyncMock(return_value=True),
        ),
    ):
        resp = await client.delete(
            f"/v1/admin/users/{_USER_ROW['id']}",
            headers={"X-API-Key": ADMIN_KEY},
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["deactivated"] is True


@pytest.mark.asyncio
async def test_deactivate_user_not_found(client):
    with (
        patch(
            "api.routers.admin.authenticate_by_api_key",
            new=AsyncMock(side_effect=_auth_side_effect),
        ),
        patch(
            "api.services.admin.deactivate_user",
            new=AsyncMock(return_value=False),
        ),
    ):
        resp = await client.delete(
            "/v1/admin/users/nonexistent",
            headers={"X-API-Key": ADMIN_KEY},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_deactivate_user_non_admin_gets_403(client):
    with patch(
        "api.routers.admin.authenticate_by_api_key",
        new=AsyncMock(side_effect=_auth_side_effect),
    ):
        resp = await client.delete(
            f"/v1/admin/users/{_USER_ROW['id']}",
            headers={"X-API-Key": NON_ADMIN_KEY},
        )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# /admin/stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_stats(client):
    stats = {
        "total_users": 10,
        "active_users": 8,
        "admin_users": 2,
        "total_chats": 500,
        "total_searches": 1200,
        "total_feedback": 80,
    }
    with (
        patch(
            "api.routers.admin.authenticate_by_api_key",
            new=AsyncMock(side_effect=_auth_side_effect),
        ),
        patch(
            "api.services.admin.get_system_stats",
            new=AsyncMock(return_value=stats),
        ),
    ):
        resp = await client.get(
            "/v1/admin/stats",
            headers={"X-API-Key": ADMIN_KEY},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["total_users"] == 10
    assert body["data"]["active_users"] == 8
    assert body["data"]["admin_users"] == 2


@pytest.mark.asyncio
async def test_system_stats_non_admin_gets_403(client):
    with patch(
        "api.routers.admin.authenticate_by_api_key",
        new=AsyncMock(side_effect=_auth_side_effect),
    ):
        resp = await client.get(
            "/v1/admin/stats",
            headers={"X-API-Key": NON_ADMIN_KEY},
        )
    assert resp.status_code == 403
