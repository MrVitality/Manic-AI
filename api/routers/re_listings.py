"""Real estate listing CRUD + content generation kickoff.

Phase 2 of the RE pivot. Manages MLS-style listing records and triggers
the content_generator agent to produce social/marketing content drafts
into re.content_calendar (which re_content.py owns).

Endpoints:
  POST   /re/listings                     -- create listing
  GET    /re/listings                     -- paginated, filterable list
  GET    /re/listings/{id}                -- single listing + content count
  PATCH  /re/listings/{id}                -- partial update
  DELETE /re/listings/{id}                -- delete (content rows survive
                                             via ON DELETE SET NULL)
  POST   /re/listings/{id}/generate-content
                                          -- run content_generator + persist
                                             variants into re.content_calendar

The /generate-content endpoint runs synchronously and may take 60+ seconds
on Ollama. This is a Phase 2 simplification -- in Phase 3 it should become
a background job (see api/routers/ingest.py for the pattern).
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from api.config import settings
from api.database import get_db
from api.http_client import get_client
from api.middleware.rate_limit import limiter
from api.schemas.envelope import ok

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/re")


# =============================================================================
# Schemas
# =============================================================================
LISTING_STATUSES = {"active", "pending", "sold", "expired", "withdrawn", "draft"}
LISTING_SOURCES = {"manual", "scraper", "idx", "import"}


class ListingCreate(BaseModel):
    address: str = Field(..., min_length=1, max_length=500)
    city: Optional[str] = Field(default=None, max_length=200)
    state: Optional[str] = Field(default="NY", max_length=10)
    zip: Optional[str] = Field(default=None, max_length=20)
    beds: Optional[int] = Field(default=None, ge=0, le=100)
    baths: Optional[float] = Field(default=None, ge=0, le=100)
    sqft: Optional[int] = Field(default=None, ge=0)
    list_price: Optional[int] = Field(default=None, ge=0)
    list_date: Optional[date] = None
    status: Optional[str] = Field(default="draft")
    days_on_market: Optional[int] = Field(default=None, ge=0)
    key_features: Optional[list[str]] = None
    description: Optional[str] = Field(default=None, max_length=10000)
    mls_number: Optional[str] = Field(default=None, max_length=100)
    agent_notes: Optional[str] = Field(default=None, max_length=4000)
    source: Optional[str] = Field(default="manual")


class ListingUpdate(BaseModel):
    address: Optional[str] = Field(default=None, min_length=1, max_length=500)
    city: Optional[str] = Field(default=None, max_length=200)
    state: Optional[str] = Field(default=None, max_length=10)
    zip: Optional[str] = Field(default=None, max_length=20)
    beds: Optional[int] = Field(default=None, ge=0, le=100)
    baths: Optional[float] = Field(default=None, ge=0, le=100)
    sqft: Optional[int] = Field(default=None, ge=0)
    list_price: Optional[int] = Field(default=None, ge=0)
    list_date: Optional[date] = None
    status: Optional[str] = None
    days_on_market: Optional[int] = Field(default=None, ge=0)
    key_features: Optional[list[str]] = None
    description: Optional[str] = Field(default=None, max_length=10000)
    mls_number: Optional[str] = Field(default=None, max_length=100)
    agent_notes: Optional[str] = Field(default=None, max_length=4000)


# =============================================================================
# Helpers
# =============================================================================
def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _row_to_summary(row: asyncpg.Record) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "address": row["address"],
        "city": row["city"],
        "state": row["state"],
        "zip": row["zip"],
        "beds": row["beds"],
        "baths": float(row["baths"]) if row["baths"] is not None else None,
        "sqft": row["sqft"],
        "list_price": row["list_price"],
        "list_date": _iso(row["list_date"]),
        "status": row["status"],
        "days_on_market": row["days_on_market"],
        "mls_number": row["mls_number"],
        "source": row["source"],
        "content_generated": row["content_generated"],
        "created_at": _iso(row["created_at"]),
    }


def _row_to_detail(row: asyncpg.Record) -> dict[str, Any]:
    summary = _row_to_summary(row)
    summary.update(
        {
            "key_features": list(row["key_features"] or []),
            "description": row["description"],
            "agent_notes": row["agent_notes"],
            "rag_collection_id": str(row["rag_collection_id"])
            if row["rag_collection_id"]
            else None,
            "updated_at": _iso(row["updated_at"]),
        }
    )
    return summary


def _validate_status(status: Optional[str]) -> None:
    if status is not None and status not in LISTING_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {sorted(LISTING_STATUSES)}",
        )


def _validate_source(source: Optional[str]) -> None:
    if source is not None and source not in LISTING_SOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source. Must be one of: {sorted(LISTING_SOURCES)}",
        )


# =============================================================================
# Routes
# =============================================================================
@router.post("/listings", response_model=None, tags=["re-listings"])
@limiter.limit(f"{settings.RATE_LIMIT_MUTATIONS_PER_MINUTE}/minute")
async def create_listing(
    request: Request,
    payload: ListingCreate,
    pool: asyncpg.Pool = Depends(get_db),
):
    """Create a listing via manual entry."""
    _validate_status(payload.status)
    _validate_source(payload.source)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO re.listings (
                address, city, state, zip,
                beds, baths, sqft, list_price, list_date,
                status, days_on_market, key_features, description,
                mls_number, agent_notes, source
            ) VALUES (
                $1, $2, $3, $4,
                $5, $6, $7, $8, $9,
                $10, $11, $12::text[], $13,
                $14, $15, $16
            )
            RETURNING *
            """,
            payload.address,
            payload.city,
            payload.state,
            payload.zip,
            payload.beds,
            payload.baths,
            payload.sqft,
            payload.list_price,
            payload.list_date,
            payload.status,
            payload.days_on_market,
            list(payload.key_features) if payload.key_features else None,
            payload.description,
            payload.mls_number,
            payload.agent_notes,
            payload.source,
        )

    logger.info("re.listing created: id=%s address=%s", row["id"], payload.address)
    return ok(_row_to_detail(row))


@router.get("/listings", response_model=None, tags=["re-listings"])
async def list_listings(
    status: Optional[str] = Query(default=None, max_length=20),
    city: Optional[str] = Query(default=None, max_length=200),
    source: Optional[str] = Query(default=None, max_length=20),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    pool: asyncpg.Pool = Depends(get_db),
):
    """List listings, newest first, filterable by status/city/source."""
    if status is not None and status not in LISTING_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status filter")
    if source is not None and source not in LISTING_SOURCES:
        raise HTTPException(status_code=400, detail="Invalid source filter")

    where: list[str] = []
    args: list[Any] = []
    if status:
        args.append(status)
        where.append(f"status = ${len(args)}")
    if city:
        args.append(city)
        where.append(f"city = ${len(args)}")
    if source:
        args.append(source)
        where.append(f"source = ${len(args)}")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    args_with_paging = args + [limit, offset]
    limit_pos = len(args) + 1
    offset_pos = len(args) + 2

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT *
            FROM re.listings
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ${limit_pos} OFFSET ${offset_pos}
            """,
            *args_with_paging,
        )
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM re.listings {where_sql}",
            *args,
        )

    return ok(
        [_row_to_summary(r) for r in rows],
        meta={"total": total, "limit": limit, "offset": offset},
    )


@router.get("/listings/{listing_id}", response_model=None, tags=["re-listings"])
async def get_listing(
    listing_id: str,
    pool: asyncpg.Pool = Depends(get_db),
):
    """Get a single listing with its content calendar count."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM re.listings WHERE id = $1",
            listing_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Listing not found")

        content_count = await conn.fetchval(
            "SELECT COUNT(*) FROM re.content_calendar WHERE listing_id = $1",
            listing_id,
        )

    detail = _row_to_detail(row)
    detail["content_calendar_count"] = int(content_count or 0)
    return ok(detail)


@router.patch("/listings/{listing_id}", response_model=None, tags=["re-listings"])
@limiter.limit(f"{settings.RATE_LIMIT_MUTATIONS_PER_MINUTE}/minute")
async def update_listing(
    request: Request,
    listing_id: str,
    payload: ListingUpdate,
    pool: asyncpg.Pool = Depends(get_db),
):
    """Partial update -- only fields explicitly set are applied."""
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "status" in updates:
        _validate_status(updates["status"])

    set_clauses: list[str] = []
    args: list[Any] = []
    for field, value in updates.items():
        args.append(value)
        if field == "key_features":
            set_clauses.append(f"{field} = ${len(args)}::text[]")
        else:
            set_clauses.append(f"{field} = ${len(args)}")
    set_clauses.append("updated_at = NOW()")
    args.append(listing_id)

    sql = f"""
        UPDATE re.listings
        SET {', '.join(set_clauses)}
        WHERE id = ${len(args)}
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, *args)
        if row is None:
            raise HTTPException(status_code=404, detail="Listing not found")

    logger.info("re.listing updated: id=%s fields=%s", listing_id, list(updates.keys()))
    return ok(_row_to_detail(row))


@router.delete("/listings/{listing_id}", response_model=None, tags=["re-listings"])
@limiter.limit(f"{settings.RATE_LIMIT_MUTATIONS_PER_MINUTE}/minute")
async def delete_listing(
    request: Request,
    listing_id: str,
    pool: asyncpg.Pool = Depends(get_db),
):
    """Delete a listing. Content calendar rows survive via ON DELETE SET NULL."""
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM re.listings WHERE id = $1",
            listing_id,
        )
    if result.endswith(" 0"):
        raise HTTPException(status_code=404, detail="Listing not found")

    logger.info("re.listing deleted: id=%s", listing_id)
    return ok({"status": "deleted", "listing_id": listing_id})


@router.post(
    "/listings/{listing_id}/generate-content",
    response_model=None,
    tags=["re-listings"],
)
@limiter.limit(f"{settings.RATE_LIMIT_MUTATIONS_PER_MINUTE}/minute")
async def generate_listing_content(
    request: Request,
    listing_id: str,
    pool: asyncpg.Pool = Depends(get_db),
):
    """Run the content_generator agent on a listing.

    Phase 2: synchronous. May take 60+ seconds on Ollama. The frontend
    is expected to wait. In Phase 3 this should be migrated to a
    background job (see api/routers/ingest.py for the pattern).
    """
    # Lazy import -- the content_generator service is owned by another
    # agent and may not exist at import time during parallel development.
    try:
        from api.services.content_generator import (  # type: ignore
            ListingInput,
            generate_content,
        )
    except ImportError as exc:
        logger.error("content_generator not available: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Content generation service unavailable",
        ) from exc

    async with pool.acquire() as conn:
        listing = await conn.fetchrow(
            "SELECT * FROM re.listings WHERE id = $1",
            listing_id,
        )
        if listing is None:
            raise HTTPException(status_code=404, detail="Listing not found")

    # Required fields for content generation. Reject listings missing them
    # rather than passing zeros -- the generator needs real numbers to
    # produce defensible copy.
    missing = [
        f for f in ("address", "city", "beds", "baths", "list_price")
        if listing[f] is None
    ]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Listing is missing required fields for content generation: {', '.join(missing)}",
        )

    listing_input = ListingInput(
        address=listing["address"],
        city=listing["city"],
        beds=int(listing["beds"]),
        baths=float(listing["baths"]),
        sqft=int(listing["sqft"]) if listing["sqft"] is not None else None,
        list_price=int(listing["list_price"]),
        key_features=tuple(listing["key_features"] or ()),
        agent_notes=listing["agent_notes"],
    )

    client = get_client()
    try:
        variants = await generate_content(listing_input, client)
    except Exception as exc:
        logger.exception("Content generation failed for listing %s", listing_id)
        raise HTTPException(
            status_code=502,
            detail=f"Content generation failed: {exc}",
        ) from exc

    summary: dict[str, int] = {"total": 0, "draft": 0, "flagged": 0, "blocked": 0}
    created_ids: list[str] = []

    async with pool.acquire() as conn:
        async with conn.transaction():
            for variant in variants:
                verdict = getattr(variant, "fair_housing_verdict", None)
                fh_verdict = getattr(verdict, "verdict", None) if verdict else None
                fh_notes = getattr(verdict, "audit_log", None) if verdict else None
                # Verdict may already be a flat string; tolerate both shapes.
                if isinstance(verdict, str):
                    fh_verdict = verdict
                    fh_notes = None

                generated_by = getattr(variant, "generated_by", None) or getattr(
                    settings, "OLLAMA_MODEL", "ollama"
                )

                row = await conn.fetchrow(
                    """
                    INSERT INTO re.content_calendar (
                        listing_id, platform, content_type, status,
                        title, content, hashtags, image_notes,
                        generated_by, compliance_checked_at,
                        fair_housing_notes, fair_housing_verdict
                    ) VALUES (
                        $1, $2, 'listing', $3,
                        $4, $5, $6, $7,
                        $8, NOW(),
                        $9, $10
                    )
                    RETURNING id, status
                    """,
                    listing_id,
                    variant.platform,
                    variant.status,
                    getattr(variant, "title", None),
                    variant.body,
                    getattr(variant, "hashtags", None),
                    getattr(variant, "image_notes", None),
                    generated_by,
                    fh_notes,
                    fh_verdict,
                )
                created_ids.append(str(row["id"]))
                summary["total"] += 1
                bucket = row["status"] if row["status"] in summary else "draft"
                summary[bucket] = summary.get(bucket, 0) + 1

            await conn.execute(
                "UPDATE re.listings SET content_generated = TRUE, updated_at = NOW() WHERE id = $1",
                listing_id,
            )

            await conn.execute(
                """
                INSERT INTO re.interactions (
                    type, body, direction, automated, workflow_id, metadata
                ) VALUES (
                    'note', $1, 'outbound', TRUE,
                    'api:re_listings.generate_content', $2::jsonb
                )
                """,
                f"Generated {summary['total']} content variants, {summary.get('flagged', 0)} flagged",
                json.dumps({"listing_id": listing_id, "summary": summary}),
            )

    logger.info(
        "re.listing content generated: id=%s total=%d flagged=%d blocked=%d",
        listing_id,
        summary["total"],
        summary.get("flagged", 0),
        summary.get("blocked", 0),
    )

    return ok({"created_ids": created_ids, "summary": summary})
