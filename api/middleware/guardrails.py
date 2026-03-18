"""Prompt injection detection middleware for chat and search endpoints."""

import base64
import logging
import re
import time
from typing import List, Tuple

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from api.config import settings

logger = logging.getLogger("api.guardrails")

# ---------------------------------------------------------------------------
# Injection patterns (pattern, weight, label)
# ---------------------------------------------------------------------------
_INJECTION_PATTERNS: List[Tuple[re.Pattern, float, str]] = [
    (re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE), 0.9, "ignore_previous"),
    (re.compile(r"system\s*prompt\s*:", re.IGNORECASE), 0.8, "system_prompt_leak"),
    (re.compile(r"you\s+are\s+now\b", re.IGNORECASE), 0.7, "role_override"),
    (re.compile(r"forget\s+everything", re.IGNORECASE), 0.9, "forget_everything"),
    (re.compile(r"disregard\s+(all\s+)?(your\s+)?(previous|prior|above)", re.IGNORECASE), 0.9, "disregard"),
    (re.compile(r"new\s+instructions\s*:", re.IGNORECASE), 0.8, "new_instructions"),
    (re.compile(r"do\s+not\s+follow\s+(your|the)\s+(previous|original)", re.IGNORECASE), 0.8, "override_instructions"),
    (re.compile(r"pretend\s+you\s+are", re.IGNORECASE), 0.6, "pretend_role"),
    (re.compile(r"act\s+as\s+(if\s+you\s+are\s+)?a\s+different", re.IGNORECASE), 0.6, "act_as_different"),
    (re.compile(r"reveal\s+(your|the)\s+(system|initial)\s+prompt", re.IGNORECASE), 0.8, "reveal_prompt"),
    (re.compile(r"\[INST\]|\[\/INST\]|<<SYS>>|<\|im_start\|>", re.IGNORECASE), 0.7, "template_injection"),
]

# Guarded endpoints (method, path)
_GUARDED_ENDPOINTS = {
    ("POST", "/v1/chat"),
    ("POST", "/v1/search"),
}

# Maximum body size to scan (64 KB) -- avoid scanning huge file uploads
_MAX_SCAN_BYTES = 65_536


def _decode_base64_fragments(text: str) -> str:
    """Attempt to decode base64-encoded fragments embedded in the text."""
    decoded_parts: list[str] = []
    for match in re.finditer(r"[A-Za-z0-9+/]{20,}={0,2}", text):
        try:
            raw = base64.b64decode(match.group(), validate=True)
            decoded_parts.append(raw.decode("utf-8", errors="ignore"))
        except Exception:
            continue
    return " ".join(decoded_parts)


def _decode_unicode_escapes(text: str) -> str:
    """Decode common unicode escape sequences (\\uXXXX, \\xXX)."""
    try:
        return text.encode("utf-8").decode("unicode_escape", errors="ignore")
    except Exception:
        return text


def score_injection(text: str) -> Tuple[float, str]:
    """Score a text for prompt injection patterns.

    Returns (score, matched_label) where score is 0.0-1.0.
    """
    if not text:
        return 0.0, ""

    best_score = 0.0
    best_label = ""

    # Check the original text
    for pattern, weight, label in _INJECTION_PATTERNS:
        if pattern.search(text):
            if weight > best_score:
                best_score = weight
                best_label = label

    # Check base64-decoded fragments
    decoded_b64 = _decode_base64_fragments(text)
    if decoded_b64:
        for pattern, weight, label in _INJECTION_PATTERNS:
            if pattern.search(decoded_b64):
                if weight > best_score:
                    best_score = weight
                    best_label = f"base64_{label}"

    # Check unicode-escaped content
    decoded_unicode = _decode_unicode_escapes(text)
    if decoded_unicode != text:
        for pattern, weight, label in _INJECTION_PATTERNS:
            if pattern.search(decoded_unicode):
                if weight > best_score:
                    best_score = weight
                    best_label = f"unicode_{label}"

    return min(best_score, 1.0), best_label


class GuardrailsMiddleware(BaseHTTPMiddleware):
    """Scan incoming request bodies on guarded endpoints for prompt injection.

    Lightweight pattern matching -- adds <5 ms overhead per request.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not settings.GUARDRAILS_ENABLED:
            return await call_next(request)

        endpoint_key = (request.method, request.url.path)
        if endpoint_key not in _GUARDED_ENDPOINTS:
            return await call_next(request)

        start = time.perf_counter()

        # Read and cache the body so downstream handlers can still access it
        body_bytes = await request.body()
        body_text = body_bytes[:_MAX_SCAN_BYTES].decode("utf-8", errors="ignore")

        injection_score, matched_label = score_injection(body_text)

        scan_ms = (time.perf_counter() - start) * 1000.0

        if injection_score > 0.7:
            truncated_input = body_text[:200].replace("\n", " ")
            logger.warning(
                "Blocked prompt injection: score=%.2f label=%s path=%s scan_ms=%.2f input=%r",
                injection_score,
                matched_label,
                request.url.path,
                scan_ms,
                truncated_input,
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Request blocked by security guardrails",
                    "code": "INJECTION_DETECTED",
                },
            )

        return await call_next(request)
