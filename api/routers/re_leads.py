"""Real estate lead intake and CRUD.

Phase 1 of the RE pivot. Handles the full intake flow:
  POST /v1/re/leads/intake  -- public-ish webhook target (Seller Blueprint,
                               forms, etc.) that scores + persists a new lead
  GET  /v1/re/leads          -- paginated list, filterable by tier/source
  GET  /v1/re/leads/{id}     -- single lead + recent interactions

Scoring is synchronous on intake (Ollama p50 ~2s on llama3.2:3b). If scoring
fails, the lead is still persisted with a fallback tier='warm' so it never
drops on the floor.

Downstream: n8n WF02 polls `re.v_hot_leads` for instant email triggers; WF03
polls `re.v_drip_due_today` for daily drip sends. This router does NOT send
email itself -- that's n8n's job.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field

from api.config import settings
from api.database import get_db
from api.http_client import get_client
from api.middleware.rate_limit import limiter
from api.schemas.envelope import ok
from api.services.lead_scoring import LeadInput, score_lead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/re")


# =============================================================================
# Schemas
# =============================================================================
class LeadIntakeRequest(BaseModel):
    """Incoming lead payload. Kept generous to match heterogeneous webhooks."""

    name: str = Field(..., min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=50)
    source: Optional[str] = Field(default="website", max_length=50)
    source_funnel: Optional[str] = Field(default=None, max_length=100)
    message: Optional[str] = Field(default=None, max_length=4000)
    property_interest: Optional[str] = Field(default=None, max_length=500)
    timeline: Optional[str] = Field(default=None, max_length=200)
    buyer_seller: Optional[str] = Field(default=None, max_length=20)
    raw_payload: Optional[dict[str, Any]] = None


class LeadSummary(BaseModel):
    id: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    source: Optional[str]
    tier: Optional[str]
    score: Optional[int]
    property_interest: Optional[str]
    timeline: Optional[str]
    last_contacted: Optional[str]
    next_follow_up: Optional[str]
    created_at: str


# =============================================================================
# Helpers
# =============================================================================
def _row_to_summary(row: asyncpg.Record) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "email": row["email"],
        "phone": row["phone"],
        "source": row["source"],
        "tier": row["tier"],
        "score": row["score"],
        "property_interest": row["property_interest"],
        "timeline": row["timeline"],
        "last_contacted": row["last_contacted"].isoformat() if row["last_contacted"] else None,
        "next_follow_up": row["next_follow_up"].isoformat() if row["next_follow_up"] else None,
        "created_at": row["created_at"].isoformat(),
    }


def _row_to_detail(row: asyncpg.Record) -> dict[str, Any]:
    summary = _row_to_summary(row)
    summary.update(
        {
            "message": row["message"],
            "buyer_seller": row["buyer_seller"],
            "score_reasoning": row["score_reasoning"],
            "suggested_tone": row["suggested_tone"],
            "drip_stage": row["drip_stage"],
            "tags": list(row["tags"] or []),
            "notes": row["notes"],
            "source_funnel": row["source_funnel"],
            "contact_id": str(row["contact_id"]) if row["contact_id"] else None,
            "updated_at": row["updated_at"].isoformat(),
        }
    )
    return summary


# =============================================================================
# Routes
# =============================================================================
@router.post("/leads/intake", response_model=None, tags=["re-leads"])
@limiter.limit(f"{settings.RATE_LIMIT_MUTATIONS_PER_MINUTE}/minute")
async def intake_lead(
    request: Request,
    payload: LeadIntakeRequest,
    pool: asyncpg.Pool = Depends(get_db),
):
    """Score and persist an incoming lead.

    Idempotency: no dedup on intake -- every POST creates a new row. Dedup
    lives in the downstream funnel when we merge leads into contacts.
    """
    client = get_client()
    score_input = LeadInput(
        name=payload.name,
        source=payload.source,
        message=payload.message,
        property_interest=payload.property_interest,
        timeline=payload.timeline,
        buyer_seller=payload.buyer_seller,
    )

    try:
        score = await score_lead(score_input, client)
    except Exception as exc:  # defense-in-depth; score_lead already catches
        logger.exception("Unexpected scoring error: %s", exc)
        raise HTTPException(status_code=500, detail="Scoring failed") from exc

    raw_payload_json = json.dumps(payload.raw_payload) if payload.raw_payload is not None else None

    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO re.leads (
                    name, email, phone, source, source_funnel, message,
                    property_interest, timeline, buyer_seller,
                    score, tier, score_reasoning, suggested_tone, tags,
                    raw_payload
                ) VALUES (
                    $1, $2, $3, $4, $5, $6,
                    $7, $8, $9,
                    $10, $11, $12, $13, $14::text[],
                    $15::jsonb
                )
                RETURNING *
                """,
                payload.name,
                payload.email,
                payload.phone,
                payload.source,
                payload.source_funnel,
                payload.message,
                payload.property_interest,
                payload.timeline,
                payload.buyer_seller,
                score.score,
                score.tier,
                score.reasoning,
                score.suggested_tone,
                list(score.tags),
                raw_payload_json,
            )

            await conn.execute(
                """
                INSERT INTO re.interactions (
                    lead_id, type, body, direction, automated, workflow_id, metadata
                ) VALUES ($1, 'score_update', $2, 'outbound', TRUE, 'api:re_leads.intake', $3::jsonb)
                """,
                row["id"],
                f"Intake score {score.score}/{score.tier}: {score.reasoning}",
                json.dumps(
                    {
                        "score": score.score,
                        "tier": score.tier,
                        "suggested_tone": score.suggested_tone,
                        "next_action": score.next_action,
                        "tags": list(score.tags),
                    }
                ),
            )

    logger.info(
        "re.lead intake: id=%s name=%s source=%s score=%d tier=%s",
        row["id"], payload.name, payload.source, score.score, score.tier,
    )
    return ok(_row_to_detail(row))


@router.get("/leads", response_model=None, tags=["re-leads"])
async def list_leads(
    tier: Optional[str] = Query(default=None, pattern="^(hot|warm|cold|converted|disqualified)$"),
    source: Optional[str] = Query(default=None, max_length=50),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    pool: asyncpg.Pool = Depends(get_db),
):
    """List leads, newest first, filterable by tier and source."""
    where = []
    args: list[Any] = []
    if tier:
        args.append(tier)
        where.append(f"tier = ${len(args)}")
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
            SELECT id, name, email, phone, source, tier, score,
                   property_interest, timeline, last_contacted, next_follow_up,
                   created_at
            FROM re.leads
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ${limit_pos} OFFSET ${offset_pos}
            """,
            *args_with_paging,
        )
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM re.leads {where_sql}",
            *args,
        )

    return ok(
        [_row_to_summary(r) for r in rows],
        meta={"total": total, "limit": limit, "offset": offset},
    )


@router.get("/leads/{lead_id}", response_model=None, tags=["re-leads"])
async def get_lead(
    lead_id: str,
    pool: asyncpg.Pool = Depends(get_db),
):
    """Get a single lead with its most recent interactions."""
    async with pool.acquire() as conn:
        lead_row = await conn.fetchrow(
            "SELECT * FROM re.leads WHERE id = $1",
            lead_id,
        )
        if lead_row is None:
            raise HTTPException(status_code=404, detail="Lead not found")

        interactions = await conn.fetch(
            """
            SELECT id, type, subject, body, direction, automated,
                   workflow_id, created_at
            FROM re.interactions
            WHERE lead_id = $1
            ORDER BY created_at DESC
            LIMIT 50
            """,
            lead_id,
        )

    return ok(
        {
            **_row_to_detail(lead_row),
            "interactions": [
                {
                    "id": str(i["id"]),
                    "type": i["type"],
                    "subject": i["subject"],
                    "body": i["body"],
                    "direction": i["direction"],
                    "automated": i["automated"],
                    "workflow_id": i["workflow_id"],
                    "created_at": i["created_at"].isoformat(),
                }
                for i in interactions
            ],
        }
    )
