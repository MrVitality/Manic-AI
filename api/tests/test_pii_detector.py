"""Tests for PII detection and redaction in services/pii_detector.py."""

from api.services.pii_detector import detect_pii, redact_pii


class TestDetectPii:
    def test_detects_email(self):
        findings = detect_pii("contact me at user@example.com please")
        assert len(findings) >= 1
        assert any(f["type"] == "EMAIL" for f in findings)
        assert any(f["value"] == "user@example.com" for f in findings)

    def test_detects_phone(self):
        findings = detect_pii("call me at 555-867-5309")
        assert any(f["type"] == "PHONE" for f in findings)

    def test_detects_phone_with_country_code(self):
        findings = detect_pii("reach me at +1 (800) 555-1234")
        assert any(f["type"] == "PHONE" for f in findings)

    def test_detects_ssn(self):
        findings = detect_pii("my SSN is 123-45-6789")
        assert any(f["type"] == "SSN" for f in findings)

    def test_detects_credit_card(self):
        findings = detect_pii("card number 4111-1111-1111-1111")
        assert any(f["type"] == "CREDIT_CARD" for f in findings)

    def test_detects_multiple_sorted_by_position(self):
        findings = detect_pii("email: a@b.com and SSN: 123-45-6789")
        assert len(findings) >= 2
        assert findings[0]["start"] <= findings[1]["start"]

    def test_no_pii_returns_empty(self):
        assert detect_pii("the quick brown fox") == []


class TestRedactPii:
    def test_redacts_email(self):
        result = redact_pii("email me at foo@bar.com")
        assert "foo@bar.com" not in result
        assert "[REDACTED_EMAIL]" in result

    def test_redacts_phone(self):
        result = redact_pii("call 555-867-5309")
        assert "555-867-5309" not in result
        assert "[REDACTED_PHONE]" in result

    def test_redacts_ssn(self):
        result = redact_pii("SSN: 123-45-6789")
        assert "123-45-6789" not in result
        assert "[REDACTED_SSN]" in result

    def test_redacts_multiple(self):
        result = redact_pii("email: a@b.com and SSN: 123-45-6789")
        assert "[REDACTED_EMAIL]" in result
        assert "[REDACTED_SSN]" in result

    def test_no_pii_unchanged(self):
        text = "no pii here at all"
        assert redact_pii(text) == text

    def test_preserves_surrounding_text(self):
        result = redact_pii("hello user@x.com goodbye")
        assert result.startswith("hello ")
        assert result.endswith(" goodbye")
