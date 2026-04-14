"""Listing content generator with Fair Housing critic loop.

Generator-Critic agent graph that turns a single ``ListingInput`` into 5
content variants (MLS description, Instagram caption, Facebook post, email
blast, Reels script). Each variant is run through
``api.services.fair_housing.check_compliance`` and tagged with the verdict
before being returned.

Prompts are ported verbatim from
``~/Downloads/Lead and Content Machine/06_listing_content_pipeline.json``
(WF06 - New Listing Content Pipeline). Minor template-syntax adjustments
only -- substantive copy is unchanged.

Sequential generation: the VPS runs a single Ollama process on 16 GB RAM.
``asyncio.gather`` over the 5 prompts will OOM. Variants are produced one at
a time.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Literal, Optional

import httpx

from api.config import settings
from api.services.fair_housing import FairHousingVerdict, check_compliance

logger = logging.getLogger(__name__)

Platform = Literal["mls", "instagram", "facebook", "email", "reels"]
ContentStatus = Literal["draft", "flagged", "blocked"]


# ---------------------------------------------------------------------------
# Inputs / outputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ListingInput:
    """Minimal listing data needed to drive the 5 generator prompts."""

    address: str
    city: str
    beds: int
    baths: float
    sqft: Optional[int]
    list_price: int
    key_features: tuple[str, ...]
    agent_notes: Optional[str] = None


@dataclass(frozen=True)
class ContentVariant:
    """A single generated piece of marketing content + its compliance verdict."""

    platform: Platform
    title: Optional[str]
    body: str
    hashtags: Optional[str]
    image_notes: Optional[str]
    fair_housing_verdict: FairHousingVerdict
    status: ContentStatus


# ---------------------------------------------------------------------------
# WF06 prompts -- ported verbatim from 06_listing_content_pipeline.json
# ---------------------------------------------------------------------------
#
# Each constant below corresponds to one Ollama node in the n8n workflow.
# The original n8n templating ({{ $('Normalize Listing Data').item.json.X }})
# is replaced with Python format placeholders; the surrounding instructional
# copy is unchanged.


MLS_PROMPT = (
    "You are an expert real estate copywriter specializing in New York's "
    "Capital Region. Write a compelling MLS listing description for Mark "
    "Vitale of Vera Cohen Realty.\n\n"
    "Property Details:\n"
    "- Address: {address}\n"
    "- City: {city}\n"
    "- Beds/Baths/SqFt: {beds}BR / {baths}BA / {sqft} sq ft\n"
    "- List Price: ${list_price:,}\n"
    "- Key Features: {features}\n"
    "- Neighborhood: {neighborhood}\n"
    "- Target Buyer: motivated buyer\n\n"
    "Requirements:\n"
    "- 200-250 words\n"
    "- Lead with the most compelling feature\n"
    "- Reference specific Capital Region lifestyle details where relevant "
    "(walkability, local spots, commute to state gov, etc.)\n"
    "- No Fair Housing violations (no school district references, no "
    "'perfect for families', no religious/racial/age references)\n"
    "- No unsupported superlatives ('best in class', 'one of a kind')\n"
    "- End with a call-to-action to schedule a showing\n"
    "- Tone: warm and inviting but confident\n\n"
    "Return ONLY the listing description text, no labels, no JSON."
)


INSTAGRAM_PROMPT = (
    "Write an Instagram caption for this Capital Region NY listing by Mark "
    "Vitale, real estate agent.\n\n"
    "Property: {beds}BR/{baths}BA in {city} | ${list_price:,}\n"
    "Key features: {features}\n"
    "Neighborhood: {neighborhood}\n\n"
    "Rules:\n"
    "- 100-150 words\n"
    "- Hook in first 2 lines (visible before 'more' cutoff)\n"
    "- Conversational, not corporate\n"
    "- End with: 'DM me or click the link in bio to schedule a showing'\n"
    "- Then on a new line, include 20 relevant hashtags\n"
    "- Include: #CapitalRegionRealEstate #AlbanyNY #[City]Homes #NYRealEstate "
    "#JustListed #HomesForSale #[Neighborhood if known] #MarkVitaleRealEstate\n\n"
    "Return ONLY the caption + hashtags."
)


FACEBOOK_PROMPT = (
    "Write a Facebook post for this Capital Region NY listing by Mark Vitale, "
    "Vera Cohen Realty.\n\n"
    "Property: {address} | {beds}BR/{baths}BA | ${list_price:,}\n"
    "Features: {features}\n"
    "Neighborhood notes: {neighborhood}\n\n"
    "Write a story-style Facebook post that:\n"
    "- Opens with something that feels like a neighbor telling you about a "
    "great house\n"
    "- 200-250 words\n"
    "- Includes key details organically (not as a bullet list)\n"
    "- Talks about the lifestyle the home enables, not just specs\n"
    "- Ends with: 'Comment below or message me to schedule a private showing "
    "-- these don't last long in this market!'\n"
    "- Includes 5-8 hashtags at the bottom\n\n"
    "Return ONLY the Facebook post text."
)


EMAIL_PROMPT = (
    "Write an email blast for this new listing from Mark Vitale, Vera Cohen "
    "Realty, Capital Region NY.\n\n"
    "Property: {address} | ${list_price:,} | {beds}BR/{baths}BA/{sqft}sqft\n"
    "Features: {features}\n"
    "Neighborhood: {neighborhood}\n\n"
    "Write:\n"
    "1. Subject line (max 50 chars, compelling)\n"
    "2. Email body (150-200 words)\n\n"
    "Email body should:\n"
    "- Open with urgency tied to the market (Capital Region homes move fast)\n"
    "- Highlight 3-4 key features conversationally\n"
    "- Reference neighborhood lifestyle\n"
    "- CTA: reply to schedule a showing or call (518) 533-8775\n\n"
    "Return ONLY valid JSON:\n"
    "{{\n"
    '  "subject": "<subject line>",\n'
    '  "body": "<email body>"\n'
    "}}"
)


REELS_PROMPT = (
    "Write a 30-second video script for a Reels/TikTok about this listing. "
    "Mark Vitale will speak directly to camera.\n\n"
    "Property: {beds}BR/{baths}BA in {city}, ${list_price:,}\n"
    "Top 3 features: {features}\n"
    "Neighborhood: {neighborhood}\n\n"
    "Script requirements:\n"
    "- Hook in first 3 seconds (stops the scroll)\n"
    "- 30 seconds max when spoken at normal pace (~75-90 words)\n"
    "- Mark speaks as himself -- knowledgeable local agent, not a TV presenter\n"
    "- Call to action at end: 'Link in bio or DM me to schedule a tour'\n"
    "- Written as [MARK SAYS: ...] format for teleprompter use\n"
    "- Include [B-ROLL SUGGESTION: ...] notes for what to film\n\n"
    "Return ONLY the script, no JSON."
)


# Default per-platform image notes from WF06's compile-content node.
_IMAGE_NOTES: dict[Platform, str] = {
    "mls": "For MLS upload -- no social image needed",
    "instagram": "Use best exterior photo + 2-3 interior hero shots",
    "facebook": "Album post: 6-8 photos. Cover = exterior front.",
    "email": "Include 1 hero exterior photo at top of email",
    "reels": "Film: exterior walkup, kitchen, living room, backyard. Vertical 9:16.",
}


# ---------------------------------------------------------------------------
# Ollama plumbing
# ---------------------------------------------------------------------------


async def _call_ollama(
    prompt: str,
    client: httpx.AsyncClient,
    *,
    model: Optional[str],
    timeout: float = 90.0,
) -> str:
    """Single Ollama chat call. Returns the message content (possibly empty)."""
    response = await client.post(
        f"{settings.OLLAMA_URL}/api/chat",
        json={
            "model": model or settings.CHAT_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.6},
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json().get("message", {}).get("content", "") or ""


def _format_listing_vars(listing: ListingInput) -> dict[str, object]:
    return {
        "address": listing.address,
        "city": listing.city,
        "beds": listing.beds,
        "baths": listing.baths,
        "sqft": listing.sqft if listing.sqft is not None else "N/A",
        "list_price": listing.list_price,
        "features": ", ".join(listing.key_features) if listing.key_features else "n/a",
        "neighborhood": listing.agent_notes or "Capital Region NY",
    }


def _status_for(verdict: FairHousingVerdict) -> ContentStatus:
    if verdict.verdict == "block":
        return "blocked"
    if verdict.verdict == "warn":
        return "flagged"
    return "draft"


def _parse_email_payload(raw: str) -> tuple[Optional[str], str]:
    """Pull (subject, body) out of an LLM email response. Tolerant to garbage."""
    cleaned = raw.strip()
    # Strip markdown fences if the model wrapped them.
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()
    try:
        data = json.loads(cleaned)
        return (
            str(data.get("subject") or "New Listing Available").strip() or None,
            str(data.get("body") or raw).strip(),
        )
    except (json.JSONDecodeError, AttributeError):
        return ("New Listing Available", raw.strip())


# ---------------------------------------------------------------------------
# Variant builders
# ---------------------------------------------------------------------------


async def _generate_one(
    platform: Platform,
    prompt: str,
    listing: ListingInput,
    client: httpx.AsyncClient,
    *,
    model: Optional[str],
) -> ContentVariant:
    """Generate a single variant + run it through compliance."""
    try:
        raw = await _call_ollama(prompt, client, model=model)
    except httpx.HTTPError as exc:
        logger.warning("Content generation failed for %s: %s", platform, exc)
        raw = ""

    title: Optional[str] = None
    body: str = raw.strip()
    hashtags: Optional[str] = None

    if platform == "email":
        title, body = _parse_email_payload(raw)
    elif platform in ("instagram", "facebook"):
        title = f"Just Listed: {listing.address}"
        # Extract trailing hashtag block when present.
        if "#" in body:
            tag_index = body.rfind("\n#")
            if tag_index == -1:
                tag_index = body.find("#")
            if tag_index != -1:
                hashtags = body[tag_index:].strip()
    elif platform == "mls":
        title = f"MLS Description: {listing.address}"
    elif platform == "reels":
        title = f"Listing Reel Script: {listing.address}"

    # Run compliance against the actual marketing body (and subject when present).
    compliance_text = body if not title or platform != "email" else f"{title}\n\n{body}"
    verdict = await check_compliance(compliance_text, client)

    return ContentVariant(
        platform=platform,
        title=title,
        body=body,
        hashtags=hashtags,
        image_notes=_IMAGE_NOTES[platform],
        fair_housing_verdict=verdict,
        status=_status_for(verdict),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


_PIPELINE: tuple[tuple[Platform, str], ...] = (
    ("mls", MLS_PROMPT),
    ("instagram", INSTAGRAM_PROMPT),
    ("facebook", FACEBOOK_PROMPT),
    ("email", EMAIL_PROMPT),
    ("reels", REELS_PROMPT),
)


async def generate_content(
    listing: ListingInput,
    client: httpx.AsyncClient,
    *,
    model: Optional[str] = None,
) -> list[ContentVariant]:
    """Generate all 5 listing content variants sequentially.

    Each variant is gated through ``check_compliance`` before being returned.
    Variants are produced **sequentially** to avoid OOM on the single-Ollama
    VPS -- do not change this to ``asyncio.gather``.
    """
    variables = _format_listing_vars(listing)
    variants: list[ContentVariant] = []

    for platform, template in _PIPELINE:
        prompt = template.format(**variables)
        variant = await _generate_one(platform, prompt, listing, client, model=model)
        variants.append(variant)

    return variants


__all__ = [
    "ListingInput",
    "ContentVariant",
    "Platform",
    "ContentStatus",
    "MLS_PROMPT",
    "INSTAGRAM_PROMPT",
    "FACEBOOK_PROMPT",
    "EMAIL_PROMPT",
    "REELS_PROMPT",
    "generate_content",
]
