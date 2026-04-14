"""SEO content writer service.

Ports the ``seo-content-writer`` Claude subagent
(``~/.claude/agents/seo-content-writer.md``) into a Python service that
produces general-purpose real estate marketing copy: blog posts, email
templates, neighborhood guides, listing descriptions, and landing-page copy.

All output is run through ``api.services.fair_housing.check_compliance`` and
the function will raise ``FairHousingViolation`` if the LLM produces content
that the compliance gate marks as ``block``. ``warn`` content is returned
with a logging warning so the caller can surface it for review.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal, Optional

import httpx

from api.config import settings
from api.services.fair_housing import FairHousingVerdict, check_compliance

logger = logging.getLogger(__name__)


ContentType = Literal[
    "blog",
    "email",
    "neighborhood_guide",
    "listing_description",
    "landing_copy",
]
Audience = Literal["buyer", "seller", "investor"]
LengthHint = Literal["short", "medium", "long"]


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SEOContentRequest:
    """Input for the SEO content writer."""

    content_type: ContentType
    topic: str
    target_keywords: tuple[str, ...]
    audience: Audience
    length_hint: LengthHint = "medium"


class FairHousingViolation(RuntimeError):
    """Raised when generated content is blocked by the Fair Housing gate."""

    def __init__(self, message: str, verdict: FairHousingVerdict) -> None:
        super().__init__(message)
        self.verdict = verdict


# ---------------------------------------------------------------------------
# Prompt -- ported from ~/.claude/agents/seo-content-writer.md
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = (
    "You are a real estate SEO and content marketing specialist for Mark "
    "Vitale's real estate practice (Vera Cohen Realty, Upstate NY / Capital "
    "District market).\n\n"
    "## Core Mission\n"
    "Create high-converting, SEO-optimized content for the real estate "
    "business: landing page copy, listing descriptions, email templates, blog "
    "posts, and social media content. All content targets the Capital "
    "District market.\n\n"
    "## Market Context\n"
    "- Agent: Mark Vitale, Vera Cohen Realty\n"
    "- Market: Albany, Saratoga Springs, Troy, Schenectady, and surrounding "
    "Capital District\n"
    "- Experience: 15+ years, 200+ properties sold, 98% client satisfaction\n"
    "- License: NYS Real Estate Agent\n\n"
    "## SEO Strategy\n"
    "Target Capital District keywords: 'homes for sale Albany NY', 'Saratoga "
    "Springs real estate', 'sell my house Capital District', 'home value "
    "Albany', 'investment property Upstate NY', 'multi-family Albany', 'real "
    "estate agent Capital District', 'best realtor Albany NY'. Long-tail: "
    "neighborhood- and property-type-specific.\n\n"
    "On-page SEO checklist:\n"
    "- Single H1 with primary keyword\n"
    "- H2/H3 with secondary keywords used naturally\n"
    "- Meta description 150-155 chars with compelling CTA\n"
    "- Internal linking opportunities suggested where relevant\n\n"
    "## Brand Voice\n"
    "- Professional but approachable -- expert knowledge, friendly delivery\n"
    "- Data-driven -- back claims with numbers when possible\n"
    "- Local expertise -- deep Capital District knowledge\n"
    "- Action-oriented -- every piece of content has a clear next step\n"
    "- Authentic -- real results, real testimonials\n\n"
    "## Fair Housing\n"
    "ABSOLUTE RULE: never include language that targets, prefers, or excludes "
    "any protected class (race, color, national origin, religion, sex, "
    "familial status, disability, age, marital status, source of income, "
    "military status, sexual orientation, gender identity). No 'perfect for "
    "families', no school district selling points, no demographic descriptors "
    "of neighborhoods. Describe the property and the lifestyle, never the "
    "intended occupant."
)


_LENGTH_GUIDANCE: dict[LengthHint, str] = {
    "short": "Length: 150-300 words.",
    "medium": "Length: 400-700 words.",
    "long": "Length: 900-1500 words.",
}


_TYPE_INSTRUCTIONS: dict[ContentType, str] = {
    "blog": (
        "Format: Blog post. Open with a hook, use H2/H3 section headers, "
        "deliver value before any CTA, and close with one clear next step "
        "(contact Mark for a consultation, get a home valuation, etc.)."
    ),
    "email": (
        "Format: Email. Provide a subject line on the first line (prefix it "
        "with 'Subject:'), then a blank line, then the body. Personable, "
        "scannable, single CTA at the end."
    ),
    "neighborhood_guide": (
        "Format: Neighborhood guide. Cover lifestyle, amenities, walkability, "
        "transportation, parks, dining, and price ranges. Use H2 sections. "
        "Avoid school-quality claims and any demographic descriptors."
    ),
    "listing_description": (
        "Format: MLS-style listing description. 200-300 words. Lead with the "
        "best feature. Paint the lifestyle. End with a CTA to schedule a "
        "showing. Do NOT mention school districts."
    ),
    "landing_copy": (
        "Format: Landing page copy. Headline + subheadline + 3-5 short "
        "benefit-driven sections + final CTA block. Focus on clarity over "
        "cleverness."
    ),
}


def _build_prompt(req: SEOContentRequest) -> str:
    keywords = ", ".join(req.target_keywords) if req.target_keywords else "(none specified)"
    return (
        f"Content type: {req.content_type}\n"
        f"Topic: {req.topic}\n"
        f"Target audience: {req.audience}\n"
        f"Target keywords: {keywords}\n"
        f"{_LENGTH_GUIDANCE[req.length_hint]}\n\n"
        f"{_TYPE_INSTRUCTIONS[req.content_type]}\n\n"
        "Write the content now. Return ONLY the finished content -- no "
        "preamble, no JSON, no metadata."
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def write_seo_content(
    req: SEOContentRequest,
    client: httpx.AsyncClient,
    *,
    model: Optional[str] = None,
    timeout: float = 90.0,
) -> str:
    """Generate SEO content and run it through the Fair Housing gate.

    Returns the generated content as a string. Raises ``FairHousingViolation``
    if the compliance gate returns ``block``. Logs a warning when the gate
    returns ``warn`` (caller decides whether to display).
    """
    user_prompt = _build_prompt(req)

    try:
        response = await client.post(
            f"{settings.OLLAMA_URL}/api/chat",
            json={
                "model": model or settings.CHAT_MODEL,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "options": {"temperature": 0.7},
            },
            timeout=timeout,
        )
        response.raise_for_status()
        content = (response.json().get("message", {}).get("content") or "").strip()
    except httpx.HTTPError as exc:
        logger.warning("SEO content writer Ollama call failed: %s", exc)
        raise

    if not content:
        raise RuntimeError("SEO content writer returned empty content")

    verdict = await check_compliance(content, client)

    if verdict.verdict == "block":
        logger.error(
            "SEO content writer output blocked by Fair Housing gate: %s",
            verdict.audit_log,
        )
        raise FairHousingViolation(
            f"Generated content blocked by Fair Housing gate: {verdict.audit_log}",
            verdict=verdict,
        )

    if verdict.verdict == "warn":
        logger.warning(
            "SEO content writer output flagged for review: %s",
            verdict.audit_log,
        )

    return content


__all__ = [
    "ContentType",
    "Audience",
    "LengthHint",
    "SEOContentRequest",
    "FairHousingViolation",
    "write_seo_content",
]
