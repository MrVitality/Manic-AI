"""Regex-based PII detection and redaction for the ingestion pipeline."""

import re
from typing import Dict, List

# ---------------------------------------------------------------------------
# PII patterns
# ---------------------------------------------------------------------------

_PII_PATTERNS: List[Dict[str, re.Pattern | str]] = [
    {
        "type": "EMAIL",
        "pattern": re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
        "redaction": "[REDACTED_EMAIL]",
    },
    {
        "type": "PHONE",
        "pattern": re.compile(
            r"(?<!\d)"  # not preceded by digit
            r"(?:\+?1[\s.\-]?)?"  # optional country code
            r"(?:\(?\d{3}\)?[\s.\-]?)"  # area code
            r"\d{3}[\s.\-]?"  # exchange
            r"\d{4}"  # subscriber
            r"(?!\d)"  # not followed by digit
        ),
        "redaction": "[REDACTED_PHONE]",
    },
    {
        "type": "SSN",
        "pattern": re.compile(
            r"(?<!\d)"
            r"\d{3}[\s\-]\d{2}[\s\-]\d{4}"
            r"(?!\d)"
        ),
        "redaction": "[REDACTED_SSN]",
    },
    {
        "type": "CREDIT_CARD",
        "pattern": re.compile(
            r"(?<!\d)"
            r"(?:\d{4}[\s\-]?){3}\d{4}"
            r"(?!\d)"
        ),
        "redaction": "[REDACTED_CREDIT_CARD]",
    },
]


def detect_pii(text: str) -> List[Dict]:
    """Detect PII in text.

    Returns a list of dicts: {type, value, start, end}.
    """
    findings: List[Dict] = []

    for entry in _PII_PATTERNS:
        pattern: re.Pattern = entry["pattern"]
        pii_type: str = entry["type"]

        for match in pattern.finditer(text):
            findings.append({
                "type": pii_type,
                "value": match.group(),
                "start": match.start(),
                "end": match.end(),
            })

    # Sort by position for stable ordering
    findings.sort(key=lambda f: f["start"])
    return findings


def redact_pii(text: str) -> str:
    """Replace detected PII with redaction placeholders.

    Processes matches from end to start to preserve character offsets.
    """
    findings = detect_pii(text)

    # Work backwards so offsets remain valid
    result = text
    for finding in reversed(findings):
        redaction = ""
        for entry in _PII_PATTERNS:
            if entry["type"] == finding["type"]:
                redaction = entry["redaction"]
                break
        result = result[:finding["start"]] + redaction + result[finding["end"]:]

    return result
