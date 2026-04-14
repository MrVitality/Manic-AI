"""Fair Housing compliance gate for real estate content.

Two-layer compliance check:
  Layer 1: Deterministic regex/keyword scan against known protected-class
           language and risky phrases (federal + NY State).
  Layer 2: LLM critic that double-checks borderline content against retrieved
           HUD reference chunks from the ``re_compliance`` RAG collection.

Public entry point:
    ``check_compliance(text, client, *, skip_llm=False, db=None)``

Verdict semantics:
    - ``block``: Content must NOT be published. Permanent unless an admin
      override is applied at the routing layer (not here).
    - ``warn``: Content has potentially-risky language; requires manual review.
    - ``pass``: No detected issues at either layer.

Design rule: NEVER fail-open. If the LLM is unavailable, the verdict floor
is ``warn`` -- never ``pass``.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal, Optional

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

Verdict = Literal["pass", "warn", "block"]
Severity = Literal["low", "medium", "high"]


# ---------------------------------------------------------------------------
# Layer 1 -- protected class keyword categories
# ---------------------------------------------------------------------------
#
# Coverage rationale: the categories below cover the federal Fair Housing Act
# protected classes (race, color, national origin, religion, sex, familial
# status, disability) plus NY State protections (age, marital status, source
# of income, military status, sexual orientation, gender identity).
#
# Severity guide:
#   high   -> direct, unambiguous reference to a protected class or an
#             explicit exclusion (e.g. "no kids", "no section 8"). Must block.
#   medium -> indirect targeting that may be lawful but is high-risk and
#             needs review (e.g. "perfect for families", "young professional",
#             "walking distance" without accessibility note).
#   low    -> mild risk; flagged for awareness but doesn't push the verdict
#             past ``pass`` on its own.

_HIGH: Severity = "high"
_MEDIUM: Severity = "medium"
_LOW: Severity = "low"


FAIR_HOUSING_TERMS: dict[str, list[tuple[str, Severity]]] = {
    # --- Familial status (federal) -------------------------------------------------
    "familial_status": [
        (r"no\s+(kids|children|infants|toddlers)", _HIGH),
        (r"no\s+families", _HIGH),
        (r"adults?\s+only", _HIGH),
        (r"childless", _HIGH),
        (r"empty\s+nesters?", _MEDIUM),
        (r"perfect\s+for\s+(a\s+)?famil(y|ies)", _MEDIUM),
        (r"great\s+for\s+(kids|children|families)", _MEDIUM),
        (r"family[\s-]+oriented", _MEDIUM),
        (r"ideal\s+for\s+(a\s+)?growing\s+famil(y|ies)", _MEDIUM),
        (r"bachelor\s+pad", _MEDIUM),
        (r"singles?\s+welcome", _MEDIUM),
        (r"newlyweds?", _MEDIUM),
    ],
    # --- Age (NY State) -----------------------------------------------------------
    "age": [
        (r"55\s*\+", _HIGH),
        (r"seniors?\s+only", _HIGH),
        (r"no\s+seniors?", _HIGH),
        (r"young\s+professionals?", _MEDIUM),
        (r"mature\s+(community|buyer|adults?)", _MEDIUM),
        (r"retirees?\s+welcome", _MEDIUM),
        (r"active\s+adult", _MEDIUM),
    ],
    # --- Race / color / national origin ------------------------------------------
    "race_color_national_origin": [
        (r"whites?\s+only", _HIGH),
        (r"no\s+(blacks?|hispanics?|asians?|latinos?)", _HIGH),
        (r"\b(ethnic|black|hispanic|latino|asian|white|caucasian)\s+neighborhood", _HIGH),
        (r"\b(italian|irish|polish|jewish|chinese|korean)\s+(section|neighborhood|community|area)", _HIGH),
        (r"traditional\s+neighborhood", _LOW),
        (r"exclusive\s+neighborhood", _MEDIUM),
        (r"private\s+community", _LOW),
    ],
    # --- Religion -----------------------------------------------------------------
    "religion": [
        (r"\bchristian\s+(home|community|family|values|neighborhood)", _HIGH),
        (r"\bjewish\s+(community|center|home|neighborhood)", _HIGH),
        (r"\bmuslim\s+(community|home|neighborhood)", _HIGH),
        (r"church[\s-]+going", _HIGH),
        (r"near\s+(st\.?|saint)\s+\w+'?s?\b", _MEDIUM),
        (r"close\s+to\s+(church|mosque|synagogue|temple)", _MEDIUM),
        (r"walk\s+to\s+(church|mosque|synagogue|temple)", _MEDIUM),
    ],
    # --- Sex / gender / sexual orientation ---------------------------------------
    "sex_gender_orientation": [
        (r"\b(men|women|males?|females?)\s+only", _HIGH),
        (r"no\s+(men|women)", _HIGH),
        (r"straight\s+(only|couples?)", _HIGH),
        (r"masculine\s+(home|space)", _LOW),
        (r"feminine\s+(home|space)", _LOW),
    ],
    # --- Disability / ability -----------------------------------------------------
    "disability": [
        (r"\bhandicapped?\b", _HIGH),
        (r"\bcrippled?\b", _HIGH),
        (r"no\s+(wheelchairs?|disabled)", _HIGH),
        (r"able[\s-]?bodied", _HIGH),
        # "walking distance" is allowed but flagged low so reviewers add an
        # accessibility note. Common in MLS copy -- intentionally low severity.
        (r"walking\s+distance", _LOW),
        (r"must\s+be\s+able\s+to\s+climb", _MEDIUM),
        (r"not\s+suitable\s+for\s+wheelchairs?", _HIGH),
    ],
    # --- Source of income (NY State) ---------------------------------------------
    "source_of_income": [
        (r"no\s+section\s*8", _HIGH),
        (r"section\s*8\s+not\s+accepted", _HIGH),
        (r"no\s+(vouchers?|housing\s+assistance)", _HIGH),
        (r"no\s+(welfare|public\s+assistance)", _HIGH),
        (r"traditional\s+financing\s+only", _MEDIUM),
        (r"cash\s+buyers?\s+only", _MEDIUM),
        (r"verified\s+income\s+required", _LOW),
    ],
    # --- Marital status (NY State) ------------------------------------------------
    "marital_status": [
        (r"married\s+couples?\s+(only|preferred)", _HIGH),
        (r"no\s+single\s+(parents?|mothers?|fathers?)", _HIGH),
    ],
    # --- Military status (NY State) -----------------------------------------------
    "military_status": [
        (r"no\s+(military|veterans?)", _HIGH),
        (r"military\s+(only|preferred)", _MEDIUM),
    ],
}


# Safe reframing dictionary -- exposed so the UI can suggest rewrites.
SAFE_REFRAMINGS: dict[str, str] = {
    "perfect for families": "4 bedrooms, fenced yard, attached garage",
    "great for kids": "fenced backyard, finished basement, two-car garage",
    "family-oriented": "spacious layout with multiple bedrooms",
    "bachelor pad": "open-concept layout, modern finishes",
    "empty nester": "low-maintenance, single-level living",
    "young professional": "convenient commute, modern updates",
    "mature community": "established neighborhood",
    "55+": "see HOA documents for community age requirements",
    "no section 8": "(remove -- source of income discrimination is illegal in NY)",
    "traditional financing only": "(remove -- describe property condition instead)",
    "walking distance": "approximately X minutes on foot; also accessible by car",
    "handicapped": "accessibility features include ...",
    "near St. Mary's": "near the corner of [street] and [street]",
    "close to church": "near community amenities",
    "ethnic neighborhood": "established neighborhood with local shops and restaurants",
    "young family": "(remove -- describe the home's features instead)",
    "master bedroom": "primary bedroom",  # not a violation but a modern preference
}


# Pre-compile every pattern once at import time. word-boundary anchors are
# baked into the patterns above where appropriate.
_COMPILED: dict[str, list[tuple[re.Pattern[str], Severity]]] = {
    category: [(re.compile(pat, re.IGNORECASE), sev) for pat, sev in patterns]
    for category, patterns in FAIR_HOUSING_TERMS.items()
}


@dataclass(frozen=True)
class RuleMatch:
    """A single rule-layer match."""

    category: str
    matched_text: str
    severity: Severity
    suggested_rewrite: Optional[str] = None


@dataclass(frozen=True)
class RuleScanResult:
    """Result of the deterministic scan."""

    matches: tuple[RuleMatch, ...]
    by_category: dict[str, tuple[RuleMatch, ...]]
    highest_severity: Optional[Severity]
    confidence: float


@dataclass(frozen=True)
class LLMIssue:
    """A single issue raised by the LLM critic."""

    quote: str
    protected_class: str
    severity: Severity
    suggested_rewrite: str


@dataclass(frozen=True)
class LLMCriticResult:
    """Result of the LLM critic call."""

    verdict: Verdict
    issues: tuple[LLMIssue, ...]
    confidence: float
    used_fallback: bool = False


@dataclass(frozen=True)
class FairHousingVerdict:
    """Aggregated verdict surfaced to callers / the database."""

    verdict: Verdict
    rule_matches: tuple[RuleMatch, ...]
    llm_issues: tuple[LLMIssue, ...]
    confidence: float
    audit_log: str  # one-liner suitable for re.content_calendar.fair_housing_notes


# ---------------------------------------------------------------------------
# Layer 1 -- rule scan
# ---------------------------------------------------------------------------


def _suggested_rewrite_for(matched_text: str) -> Optional[str]:
    """Look up a safe reframing for a matched phrase (case-insensitive)."""
    needle = matched_text.strip().lower()
    if needle in SAFE_REFRAMINGS:
        return SAFE_REFRAMINGS[needle]
    # Try a partial-key match as a fallback.
    for key, value in SAFE_REFRAMINGS.items():
        if key in needle or needle in key:
            return value
    return None


def _severity_rank(sev: Severity) -> int:
    return {"low": 1, "medium": 2, "high": 3}[sev]


def _max_severity(severities: Iterable[Severity]) -> Optional[Severity]:
    items = list(severities)
    if not items:
        return None
    return max(items, key=_severity_rank)


def scan_rules(text: str) -> RuleScanResult:
    """Run the deterministic regex scan over ``text``.

    Returns a ``RuleScanResult`` with all matches grouped by category. Empty
    or whitespace-only input returns an empty result with confidence 1.0.
    """
    if not text or not text.strip():
        return RuleScanResult(
            matches=tuple(),
            by_category={},
            highest_severity=None,
            confidence=1.0,
        )

    matches: list[RuleMatch] = []
    by_category: dict[str, list[RuleMatch]] = {}

    for category, compiled in _COMPILED.items():
        for pattern, severity in compiled:
            for hit in pattern.finditer(text):
                matched = hit.group(0)
                rule = RuleMatch(
                    category=category,
                    matched_text=matched,
                    severity=severity,
                    suggested_rewrite=_suggested_rewrite_for(matched),
                )
                matches.append(rule)
                by_category.setdefault(category, []).append(rule)

    highest = _max_severity(m.severity for m in matches)

    # Confidence: high if we found a clear violation OR if we found nothing.
    # Lower if we only found ambiguous low-severity hits.
    if not matches:
        confidence = 1.0
    elif highest == "high":
        confidence = 0.95
    elif highest == "medium":
        confidence = 0.8
    else:
        confidence = 0.6

    return RuleScanResult(
        matches=tuple(matches),
        by_category={k: tuple(v) for k, v in by_category.items()},
        highest_severity=highest,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Layer 2 -- LLM critic
# ---------------------------------------------------------------------------


_LLM_SYSTEM_PROMPT = (
    "You are a Fair Housing compliance auditor for a New York State licensed "
    "real estate agent. Your job is to detect language in marketing copy that "
    "could violate the federal Fair Housing Act (FHA) or NY State Human Rights "
    "Law. Protected classes include: race, color, national origin, religion, "
    "sex, familial status, disability, age, marital status, source of income, "
    "military status, sexual orientation, and gender identity.\n\n"
    "You will be given:\n"
    "  1. The marketing content under review.\n"
    "  2. Reference chunks from official HUD / NY State guidance.\n\n"
    "Return ONLY a JSON object with this exact shape -- no prose, no markdown:\n"
    "{\n"
    '  "verdict": "pass" | "warn" | "block",\n'
    '  "issues": [\n'
    "    {\n"
    '      "quote": "<exact phrase from the content>",\n'
    '      "protected_class": "<which class>",\n'
    '      "severity": "low" | "medium" | "high",\n'
    '      "suggested_rewrite": "<a compliant alternative>"\n'
    "    }\n"
    "  ],\n"
    '  "confidence": <float 0.0 to 1.0>\n'
    "}\n\n"
    "Verdict rules:\n"
    '  - "block" = clear, unambiguous violation. Cannot be published.\n'
    '  - "warn"  = potentially risky; needs human review.\n'
    '  - "pass"  = no concerns.\n'
    "When in doubt, return warn -- never pass borderline content.\n"
)

_LLM_USER_TEMPLATE = (
    "Content under review:\n"
    "<<<\n{content}\n>>>\n\n"
    "Reference chunks from HUD / NY State guidance:\n"
    "{references}\n\n"
    "Return ONLY the JSON object."
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(content: str) -> dict[str, Any]:
    """Pull a JSON object out of an LLM response that may include prose."""
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    match = _JSON_RE.search(content)
    if not match:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(match.group(0))


def _coerce_verdict(value: Any) -> Verdict:
    candidate = str(value or "").strip().lower()
    if candidate in ("pass", "warn", "block"):
        return candidate  # type: ignore[return-value]
    return "warn"  # safe default -- never fail-open


def _coerce_severity(value: Any) -> Severity:
    candidate = str(value or "").strip().lower()
    if candidate in ("low", "medium", "high"):
        return candidate  # type: ignore[return-value]
    return "medium"


def _llm_unavailable_result(reason: str) -> LLMCriticResult:
    """Build a conservative ``warn`` result when the LLM cannot be reached."""
    return LLMCriticResult(
        verdict="warn",
        issues=(
            LLMIssue(
                quote="(LLM compliance check unavailable)",
                protected_class="llm_unavailable",
                severity="medium",
                suggested_rewrite=f"Manual review required: {reason}",
            ),
        ),
        confidence=0.4,
        used_fallback=True,
    )


async def _retrieve_compliance_context(
    text: str,
    client: httpx.AsyncClient,
    db: Any,
) -> list[str]:
    """Retrieve top HUD compliance chunks from the ``re_compliance`` collection.

    Best-effort: returns an empty list if the collection or services are
    unavailable. The LLM still runs; it just won't have reference context.
    """
    if db is None:
        return []
    # Local import to avoid a hard dependency at module import time.
    try:
        from api.services import embedding as embedding_service
        from api.services.rag import hybrid_search
    except Exception as exc:  # pragma: no cover -- defensive
        logger.debug("Compliance context retrieval not available: %s", exc)
        return []

    try:
        query_embedding = await embedding_service.embed_text(text[:2000], client)
    except Exception as exc:
        logger.debug("Compliance embedding failed: %s", exc)
        return []

    try:
        chunks = await hybrid_search(
            query_text=text[:2000],
            query_embedding=query_embedding,
            db=db,
            top_k=5,
            collection_id="re_compliance",
        )
    except Exception as exc:
        logger.debug("Compliance hybrid_search failed: %s", exc)
        return []

    return [str(c.get("content") or c.get("text") or "").strip() for c in chunks if c]


async def llm_critic(
    text: str,
    rag_context: list[str],
    client: httpx.AsyncClient,
    *,
    model: Optional[str] = None,
    timeout: float = 30.0,
) -> LLMCriticResult:
    """Run the LLM compliance critic over ``text``.

    Returns a conservative ``warn`` fallback on any error -- never pass.
    """
    if not text or not text.strip():
        return LLMCriticResult(verdict="pass", issues=tuple(), confidence=1.0)

    references_blob = (
        "\n\n".join(f"[ref {i + 1}] {chunk}" for i, chunk in enumerate(rag_context))
        if rag_context
        else "(no reference chunks available -- judge from your own training only)"
    )
    user_prompt = _LLM_USER_TEMPLATE.format(content=text, references=references_blob)

    try:
        response = await client.post(
            f"{settings.OLLAMA_URL}/api/chat",
            json={
                "model": model or settings.CHAT_MODEL,
                "messages": [
                    {"role": "system", "content": _LLM_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "options": {"temperature": 0.0},
                "format": "json",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
    except httpx.HTTPError as exc:
        logger.warning("Fair Housing LLM critic call failed: %s", exc)
        return _llm_unavailable_result(f"HTTP error: {exc.__class__.__name__}")

    try:
        parsed = _extract_json(content)
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning(
            "Fair Housing LLM critic JSON parse failed: %s -- content=%r",
            exc,
            content[:200],
        )
        return _llm_unavailable_result("malformed LLM response")

    verdict = _coerce_verdict(parsed.get("verdict"))
    raw_issues = parsed.get("issues") or []
    if not isinstance(raw_issues, list):
        raw_issues = []

    issues: list[LLMIssue] = []
    for issue in raw_issues:
        if not isinstance(issue, dict):
            continue
        issues.append(
            LLMIssue(
                quote=str(issue.get("quote") or "").strip(),
                protected_class=str(issue.get("protected_class") or "unspecified").strip(),
                severity=_coerce_severity(issue.get("severity")),
                suggested_rewrite=str(issue.get("suggested_rewrite") or "").strip(),
            )
        )

    try:
        confidence = float(parsed.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    return LLMCriticResult(
        verdict=verdict,
        issues=tuple(issues),
        confidence=confidence,
        used_fallback=False,
    )


# ---------------------------------------------------------------------------
# Public aggregation
# ---------------------------------------------------------------------------


def _aggregate_verdict(
    rule_result: RuleScanResult,
    llm_result: Optional[LLMCriticResult],
) -> tuple[Verdict, float]:
    """Combine the two layers into a single verdict + confidence.

    Rules:
      - Any HIGH-severity rule match -> block.
      - LLM says block -> block.
      - Any MEDIUM rule match -> at least warn (LLM may upgrade to block).
      - LLM says warn -> warn.
      - Otherwise -> pass.
    """
    rule_high = rule_result.highest_severity == "high"
    rule_medium = rule_result.highest_severity == "medium"
    rule_low = rule_result.highest_severity == "low"

    llm_verdict = llm_result.verdict if llm_result else None

    if rule_high or llm_verdict == "block":
        verdict: Verdict = "block"
    elif rule_medium or llm_verdict == "warn":
        verdict = "warn"
    elif rule_low:
        # Low-severity rule hit on its own (e.g. "walking distance") with no
        # LLM concern -> pass with reduced confidence. Reviewers still see it.
        verdict = "pass"
    else:
        verdict = "pass"

    # Confidence is the lower of the two layers (we trust the more cautious one).
    rule_conf = rule_result.confidence
    llm_conf = llm_result.confidence if llm_result else 1.0
    confidence = min(rule_conf, llm_conf)

    # If we had to use the LLM fallback, cap confidence so callers know to
    # treat the verdict with care.
    if llm_result and llm_result.used_fallback:
        confidence = min(confidence, 0.5)

    return verdict, confidence


def _build_audit_log(
    verdict: Verdict,
    rule_result: RuleScanResult,
    llm_result: Optional[LLMCriticResult],
) -> str:
    """Render a human-readable one-liner for content_calendar.fair_housing_notes."""
    parts: list[str] = [f"verdict={verdict}"]

    if rule_result.matches:
        cats = sorted({m.category for m in rule_result.matches})
        sev = rule_result.highest_severity or "n/a"
        parts.append(f"rules[{sev}]: {','.join(cats)}")
    else:
        parts.append("rules: clean")

    if llm_result is None:
        parts.append("llm: skipped")
    elif llm_result.used_fallback:
        parts.append("llm: unavailable (fallback=warn)")
    else:
        parts.append(f"llm: {llm_result.verdict} ({len(llm_result.issues)} issues)")

    return " | ".join(parts)


async def check_compliance(
    text: str,
    client: httpx.AsyncClient,
    *,
    skip_llm: bool = False,
    db: Any = None,
    model: Optional[str] = None,
) -> FairHousingVerdict:
    """Two-layer Fair Housing compliance check.

    Args:
        text: The marketing content to audit.
        client: An ``httpx.AsyncClient`` for Ollama / RAG calls.
        skip_llm: If True, skip the LLM critic entirely (rules only). Useful
            for unit tests or fast batch screening. Default False.
        db: Optional asyncpg pool. When provided, the LLM critic is grounded
            in the ``re_compliance`` RAG collection. Without it, the LLM
            still runs but has no reference context.
        model: Optional override for the chat model.

    Returns:
        A ``FairHousingVerdict`` with the aggregated decision, both layers'
        outputs, a confidence score, and an audit-log string.
    """
    rule_result = scan_rules(text)

    # Decide whether to call the LLM. We always call it for non-empty content
    # unless explicitly skipped, EVEN when rules already hit -- the LLM may
    # find additional issues or upgrade a warn to a block.
    llm_result: Optional[LLMCriticResult] = None
    if not skip_llm and text and text.strip():
        rag_context = await _retrieve_compliance_context(text, client, db)
        llm_result = await llm_critic(text, rag_context, client, model=model)

    verdict, confidence = _aggregate_verdict(rule_result, llm_result)
    audit_log = _build_audit_log(verdict, rule_result, llm_result)

    return FairHousingVerdict(
        verdict=verdict,
        rule_matches=rule_result.matches,
        llm_issues=(llm_result.issues if llm_result else tuple()),
        confidence=confidence,
        audit_log=audit_log,
    )


__all__ = [
    "FAIR_HOUSING_TERMS",
    "SAFE_REFRAMINGS",
    "RuleMatch",
    "RuleScanResult",
    "LLMIssue",
    "LLMCriticResult",
    "FairHousingVerdict",
    "Verdict",
    "Severity",
    "scan_rules",
    "llm_critic",
    "check_compliance",
]
