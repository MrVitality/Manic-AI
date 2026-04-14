"""Real estate lead scoring via Ollama.

Ports the scoring prompt from Lead and Content Machine WF01 into a testable
Python service. Called by `api/routers/re_leads.py` on intake and optionally
on re-score. Returns a structured `LeadScore` or a conservative fallback
when the LLM call fails or returns malformed JSON.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Literal, Optional

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

Tier = Literal["hot", "warm", "cold"]
SuggestedTone = Literal["urgent", "nurturing", "informational"]


@dataclass(frozen=True)
class LeadInput:
    """Minimal input needed to score a lead."""

    name: str
    source: Optional[str] = None
    message: Optional[str] = None
    property_interest: Optional[str] = None
    timeline: Optional[str] = None
    buyer_seller: Optional[str] = None


@dataclass(frozen=True)
class LeadScore:
    """Structured output of the scoring pipeline."""

    score: int
    tier: Tier
    reasoning: str
    suggested_tone: SuggestedTone
    tags: tuple[str, ...]
    next_action: str


_SYSTEM_PROMPT = (
    "You are an expert real estate lead scorer for Mark Vitale, a licensed "
    "real estate agent in Albany, Schenectady, Troy, and Saratoga Springs NY "
    "(Capital Region).\n\n"
    "Analyze this incoming lead and return ONLY valid JSON with no "
    "explanation, no markdown, no code blocks.\n\n"
    "Lead Data:\n"
    "- Name: {name}\n"
    "- Source: {source}\n"
    "- Message: {message}\n"
    "- Property Interest: {property_interest}\n"
    "- Timeline: {timeline}\n"
    "- Buyer/Seller: {buyer_seller}\n\n"
    "Scoring criteria:\n"
    "- Timeline under 3 months = high score boost\n"
    "- Pre-approved buyer = maximum boost\n"
    "- Specific address or neighborhood mentioned = high intent\n"
    "- Referral source = trust boost\n"
    "- Vague message with no specifics = score penalty\n"
    "- No timeline = score penalty\n"
    "- Capital Region specific knowledge (mentions Albany, Troy, Saratoga, "
    "Schenectady) = intent boost\n\n"
    "Return this exact JSON structure:\n"
    "{{\n"
    '  "score": <integer 0-100>,\n'
    '  "tier": "<hot|warm|cold>",\n'
    '  "reasoning": "<2-3 sentence explanation>",\n'
    '  "suggested_tone": "<urgent|nurturing|informational>",\n'
    '  "tags": ["<tag1>", "<tag2>"],\n'
    '  "next_action": "<specific recommended action for Mark>"\n'
    "}}\n\n"
    "Tier rules: hot=75-100, warm=40-74, cold=0-39\n"
    "Return ONLY the JSON object."
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _safe(value: Optional[str]) -> str:
    return (value or "not provided").strip() or "not provided"


def _extract_json(content: str) -> dict[str, Any]:
    """Pull a JSON object out of an LLM response that may include surrounding prose."""
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    match = _JSON_RE.search(content)
    if not match:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(match.group(0))


def _fallback_score(lead: LeadInput, reason: str) -> LeadScore:
    """Conservative fallback when the LLM fails. Marks as warm so Mark reviews."""
    return LeadScore(
        score=50,
        tier="warm",
        reasoning=f"Auto-fallback (scoring unavailable: {reason}). Manual review recommended.",
        suggested_tone="nurturing",
        tags=("unscored", "needs_review"),
        next_action="Mark: manually review this lead and re-score when Ollama is available.",
    )


def _coerce_tier(value: Any, score: int) -> Tier:
    candidate = str(value or "").strip().lower()
    if candidate in ("hot", "warm", "cold"):
        return candidate  # type: ignore[return-value]
    if score >= 75:
        return "hot"
    if score >= 40:
        return "warm"
    return "cold"


def _coerce_tone(value: Any) -> SuggestedTone:
    candidate = str(value or "").strip().lower()
    if candidate in ("urgent", "nurturing", "informational"):
        return candidate  # type: ignore[return-value]
    return "nurturing"


def _coerce_score(value: Any) -> int:
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        return 50
    return max(0, min(100, score))


async def score_lead(
    lead: LeadInput,
    client: httpx.AsyncClient,
    *,
    model: Optional[str] = None,
    timeout: float = 30.0,
) -> LeadScore:
    """Score a lead via Ollama. Returns a fallback on any failure."""
    prompt = _SYSTEM_PROMPT.format(
        name=_safe(lead.name),
        source=_safe(lead.source),
        message=_safe(lead.message),
        property_interest=_safe(lead.property_interest),
        timeline=_safe(lead.timeline),
        buyer_seller=_safe(lead.buyer_seller),
    )

    try:
        response = await client.post(
            f"{settings.OLLAMA_URL}/api/chat",
            json={
                "model": model or settings.CHAT_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.0},
                "format": "json",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
    except httpx.HTTPError as exc:
        logger.warning("Lead scoring Ollama call failed: %s", exc)
        return _fallback_score(lead, f"HTTP error: {exc.__class__.__name__}")

    try:
        parsed = _extract_json(content)
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("Lead scoring JSON parse failed: %s — content=%r", exc, content[:200])
        return _fallback_score(lead, "malformed LLM response")

    score = _coerce_score(parsed.get("score"))
    tier = _coerce_tier(parsed.get("tier"), score)
    suggested_tone = _coerce_tone(parsed.get("suggested_tone"))
    reasoning = str(parsed.get("reasoning") or "").strip() or "No reasoning provided"
    next_action = str(parsed.get("next_action") or "").strip() or "Follow up within 24 hours"

    raw_tags = parsed.get("tags") or []
    if isinstance(raw_tags, str):
        raw_tags = [raw_tags]
    tags = tuple(str(t).strip() for t in raw_tags if str(t).strip())[:8]

    return LeadScore(
        score=score,
        tier=tier,
        reasoning=reasoning,
        suggested_tone=suggested_tone,
        tags=tags,
        next_action=next_action,
    )
