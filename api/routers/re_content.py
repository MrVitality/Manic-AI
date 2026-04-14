"""Real estate content calendar CRUD + approval workflow.

Phase 2 of the RE pivot. Manages the social/marketing content drafts
produced by the content_generator agent (kicked off from re_listings.py).

Endpoints:
  GET    /re/content                 -- paginated list, filterable
  GET    /re/content/{id}            -- single row
  PATCH  /re/content/{id}            -- partial edit
  POST   /re/content/{id}/approve    -- approve (blocked if FH=block)
  POST   /re/content/{id}/reject     -- archive with rejection note
  POST   /re/content/{id}/recheck    -- re-run fair housing compliance
  DELETE /re/content/{id}            -- delete

Compliance is non-negotiable: /approve hard-fails 409 if the row's
fair_housing_verdict is 'block'.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.config import settings
from api.database import get_db
from api.http_client import get_client
from api.middleware.rate_limit import limiter
from api.schemas.envelope import fail, ok

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/re")


# =============================================================================
# Schemas
# =============================================================================
PLATFORMS = {
    "instagram", "facebook", "linkedin", "email",
    "tiktok", "youtube", "mls", "reels", "all",
}
CONTENT_STATUSES = {
    "draft", "flagged", "blocked", "approved",
    "scheduled", "posted", "archived",
}
FH_VERDICTS = {"pass", "warn", "block"}


class ContentUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=500)
    content: Optional[str] = Field(default=None, max_length=20000)
    hashtags: Optional[str] = Field(default=None, max_length=2000)
    image_notes: Optional[str] = Field(default=None, max_length=2000)
    scheduled_date: Optional[date] = None
    status: Optional[str] = None
    platform: Optional[str] = None


class ApprovalRequest(BaseModel):
    approved_by: Optional[str] = Field(default="system", max_length=200)


class RejectionRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=2000)


# =============================================================================
# Helpers
# =============================================================================
def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "listing_id": str(row["listing_id"]) if row["listing_id"] else None,
        "scheduled_date": _iso(row["scheduled_date"]),
        "platform": row["platform"],
        "content_type": row["content_type"],
        "status": row["status"],
        "title": row["title"],
        "content": row["content"],
        "hashtags": row["hashtags"],
        "image_notes": row["image_notes"],
        "source_listing": row["source_listing"],
        "generated_by": row["generated_by"],
        "posted_at": _iso(row["posted_at"]),
        "engagement_notes": row["engagement_notes"],
        "compliance_checked_at": _iso(row["compliance_checked_at"]),
        "fair_housing_notes": row["fair_housing_notes"],
        "fair_housing_verdict": row["fair_housing_verdict"],
        "approved_by": row["approved_by"],
        "approved_at": _iso(row["approved_at"]),
        "created_at": _iso(row["created_at"]),
    }


async def _fetch_or_404(conn: asyncpg.Connection, content_id: str) -> asyncpg.Record:
    row = await conn.fetchrow(
        "SELECT * FROM re.content_calendar WHERE id = $1",
        content_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Content not found")
    return row


# =============================================================================
# Routes
# =============================================================================
@router.get("/content", response_model=None, tags=["re-content"])
async def list_content(
    status: Optional[str] = Query(default=None, max_length=20),
    platform: Optional[str] = Query(default=None, max_length=20),
    listing_id: Optional[str] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    pool: asyncpg.Pool = Depends(get_db),
):
    """List content calendar rows, newest first."""
    if status is not None and status not in CONTENT_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status filter")
    if platform is not None and platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail="Invalid platform filter")

    where: list[str] = []
    args: list[Any] = []
    if status:
        args.append(status)
        where.append(f"status = ${len(args)}")
    if platform:
        args.append(platform)
        where.append(f"platform = ${len(args)}")
    if listing_id:
        args.append(listing_id)
        where.append(f"listing_id = ${len(args)}")
    if date_from:
        args.append(date_from)
        where.append(f"scheduled_date >= ${len(args)}")
    if date_to:
        args.append(date_to)
        where.append(f"scheduled_date <= ${len(args)}")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    args_with_paging = args + [limit, offset]
    limit_pos = len(args) + 1
    offset_pos = len(args) + 2

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT *
            FROM re.content_calendar
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ${limit_pos} OFFSET ${offset_pos}
            """,
            *args_with_paging,
        )
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM re.content_calendar {where_sql}",
            *args,
        )

    return ok(
        [_row_to_dict(r) for r in rows],
        meta={"total": total, "limit": limit, "offset": offset},
    )


@router.get("/content/{content_id}", response_model=None, tags=["re-content"])
async def get_content(
    content_id: str,
    pool: asyncpg.Pool = Depends(get_db),
):
    """Get a single content row."""
    async with pool.acquire() as conn:
        row = await _fetch_or_404(conn, content_id)
    return ok(_row_to_dict(row))


@router.patch("/content/{content_id}", response_model=None, tags=["re-content"])
@limiter.limit(f"{settings.RATE_LIMIT_MUTATIONS_PER_MINUTE}/minute")
async def update_content(
    request: Request,
    content_id: str,
    payload: ContentUpdate,
    pool: asyncpg.Pool = Depends(get_db),
):
    """Partial update of body/title/hashtags/scheduled_date/status/platform."""
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "status" in updates and updates["status"] not in CONTENT_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    if "platform" in updates and updates["platform"] not in PLATFORMS:
        raise HTTPException(status_code=400, detail="Invalid platform")

    set_clauses: list[str] = []
    args: list[Any] = []
    for field, value in updates.items():
        args.append(value)
        set_clauses.append(f"{field} = ${len(args)}")
    args.append(content_id)

    sql = f"""
        UPDATE re.content_calendar
        SET {', '.join(set_clauses)}
        WHERE id = ${len(args)}
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, *args)
        if row is None:
            raise HTTPException(status_code=404, detail="Content not found")

    logger.info("re.content updated: id=%s fields=%s", content_id, list(updates.keys()))
    return ok(_row_to_dict(row))


@router.post("/content/{content_id}/approve", response_model=None, tags=["re-content"])
@limiter.limit(f"{settings.RATE_LIMIT_MUTATIONS_PER_MINUTE}/minute")
async def approve_content(
    request: Request,
    content_id: str,
    payload: ApprovalRequest = ApprovalRequest(),
    pool: asyncpg.Pool = Depends(get_db),
):
    """Approve content. Hard-fails 409 if fair_housing_verdict is 'block'."""
    async with pool.acquire() as conn:
        row = await _fetch_or_404(conn, content_id)

        if row["fair_housing_verdict"] == "block":
            logger.warning(
                "re.content approve blocked by compliance: id=%s",
                content_id,
            )
            return JSONResponse(
                status_code=409,
                content=fail(
                    "blocked_by_compliance",
                    "Cannot approve content blocked by Fair Housing review",
                    meta={
                        "content_id": content_id,
                        "fair_housing_notes": row["fair_housing_notes"],
                        "fair_housing_verdict": row["fair_housing_verdict"],
                    },
                ),
            )

        approver = (payload.approved_by or "system")[:200]
        updated = await conn.fetchrow(
            """
            UPDATE re.content_calendar
            SET status = 'approved',
                approved_at = NOW(),
                approved_by = $1
            WHERE id = $2
            RETURNING *
            """,
            approver,
            content_id,
        )

    logger.info("re.content approved: id=%s by=%s", content_id, approver)
    return ok(_row_to_dict(updated))


@router.post("/content/{content_id}/reject", response_model=None, tags=["re-content"])
@limiter.limit(f"{settings.RATE_LIMIT_MUTATIONS_PER_MINUTE}/minute")
async def reject_content(
    request: Request,
    content_id: str,
    payload: RejectionRequest = RejectionRequest(),
    pool: asyncpg.Pool = Depends(get_db),
):
    """Archive content with a rejection note appended to engagement_notes."""
    timestamp = datetime.utcnow().isoformat()
    note = f"[rejected {timestamp}] {payload.reason or 'no reason provided'}"

    async with pool.acquire() as conn:
        await _fetch_or_404(conn, content_id)
        updated = await conn.fetchrow(
            """
            UPDATE re.content_calendar
            SET status = 'archived',
                engagement_notes = CASE
                    WHEN engagement_notes IS NULL OR engagement_notes = ''
                        THEN $1
                    ELSE engagement_notes || E'\n' || $1
                END
            WHERE id = $2
            RETURNING *
            """,
            note,
            content_id,
        )

    logger.info("re.content rejected: id=%s", content_id)
    return ok(_row_to_dict(updated))


@router.post("/content/{content_id}/recheck", response_model=None, tags=["re-content"])
@limiter.limit(f"{settings.RATE_LIMIT_MUTATIONS_PER_MINUTE}/minute")
async def recheck_content(
    request: Request,
    content_id: str,
    pool: asyncpg.Pool = Depends(get_db),
):
    """Re-run fair housing compliance on the current body."""
    # Lazy import -- service is owned by another agent during parallel dev.
    try:
        from api.services.fair_housing import check_compliance  # type: ignore
    except ImportError as exc:
        logger.error("fair_housing service not available: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Fair housing service unavailable",
        ) from exc

    async with pool.acquire() as conn:
        row = await _fetch_or_404(conn, content_id)

    try:
        client = get_client()
        verdict = await check_compliance(row["content"], client, db=pool)
    except Exception as exc:
        logger.exception("Fair housing recheck failed for %s", content_id)
        raise HTTPException(
            status_code=502,
            detail=f"Fair housing recheck failed: {exc}",
        ) from exc

    # Tolerate both object-with-attrs and dict shapes.
    if isinstance(verdict, dict):
        fh_verdict = verdict.get("verdict")
        fh_notes = verdict.get("audit_log") or verdict.get("notes")
    else:
        fh_verdict = getattr(verdict, "verdict", None)
        fh_notes = getattr(verdict, "audit_log", None) or getattr(verdict, "notes", None)

    if fh_verdict not in FH_VERDICTS:
        raise HTTPException(
            status_code=502,
            detail=f"Invalid fair housing verdict returned: {fh_verdict}",
        )

    # If now blocked, reflect that in status; otherwise leave status alone.
    new_status_clause = ""
    args: list[Any] = [fh_notes, fh_verdict, content_id]
    if fh_verdict == "block":
        new_status_clause = ", status = 'blocked'"
    elif fh_verdict == "warn":
        new_status_clause = ", status = CASE WHEN status IN ('approved','scheduled','posted') THEN status ELSE 'flagged' END"

    sql = f"""
        UPDATE re.content_calendar
        SET fair_housing_notes = $1,
            fair_housing_verdict = $2,
            compliance_checked_at = NOW()
            {new_status_clause}
        WHERE id = $3
        RETURNING *
    """

    async with pool.acquire() as conn:
        updated = await conn.fetchrow(sql, *args)

    logger.info(
        "re.content rechecked: id=%s verdict=%s",
        content_id,
        fh_verdict,
    )
    return ok(_row_to_dict(updated))


@router.delete("/content/{content_id}", response_model=None, tags=["re-content"])
@limiter.limit(f"{settings.RATE_LIMIT_MUTATIONS_PER_MINUTE}/minute")
async def delete_content(
    request: Request,
    content_id: str,
    pool: asyncpg.Pool = Depends(get_db),
):
    """Delete a content calendar row."""
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM re.content_calendar WHERE id = $1",
            content_id,
        )
    if result.endswith(" 0"):
        raise HTTPException(status_code=404, detail="Content not found")

    logger.info("re.content deleted: id=%s", content_id)
    return ok({"status": "deleted", "content_id": content_id})
