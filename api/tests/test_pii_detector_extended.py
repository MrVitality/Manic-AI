"""Extended edge-case tests for api/services/pii_detector.py."""

from api.services.pii_detector import detect_pii, redact_pii


class TestPiiDetectorEdgeCases:
    def test_multiple_emails_in_one_string(self):
        """All email addresses in a string are detected."""
        text = "Send to alice@example.com and bob@company.org and carol@test.io"
        findings = detect_pii(text)
        email_findings = [f for f in findings if f["type"] == "EMAIL"]
        assert len(email_findings) == 3
        values = {f["value"] for f in email_findings}
        assert "alice@example.com" in values
        assert "bob@company.org" in values
        assert "carol@test.io" in values

    def test_phone_with_dots_as_separators(self):
        """Phone numbers with dots (e.g. 555.867.5309) are detected."""
        findings = detect_pii("My number is 555.867.5309 please call")
        phone_findings = [f for f in findings if f["type"] == "PHONE"]
        assert len(phone_findings) >= 1

    def test_credit_card_without_separators(self):
        """16-digit credit card numbers without separators are detected."""
        findings = detect_pii("Pay using card 4111111111111111 today")
        cc_findings = [f for f in findings if f["type"] == "CREDIT_CARD"]
        assert len(cc_findings) >= 1

    def test_ssn_without_dashes_not_matched(self):
        """9-digit number without dashes (123456789) should NOT match SSN pattern."""
        # The SSN regex requires delimiters between groups
        findings = detect_pii("My id is 123456789")
        ssn_findings = [f for f in findings if f["type"] == "SSN"]
        assert len(ssn_findings) == 0

    def test_mixed_pii_types_in_long_paragraph(self):
        """A realistic paragraph containing multiple PII types is fully detected."""
        paragraph = (
            "Dear John, please contact our support at help@company.com or call "
            "1-800-555-1234. Your SSN on file is 987-65-4321 and the credit card "
            "we have is 4000-1234-5678-9010. We look forward to helping you."
        )
        findings = detect_pii(paragraph)
        types_found = {f["type"] for f in findings}
        assert "EMAIL" in types_found
        assert "PHONE" in types_found
        assert "SSN" in types_found
        assert "CREDIT_CARD" in types_found

    def test_redact_multiple_emails(self):
        """All emails in a string are replaced with redaction placeholders."""
        text = "alice@a.com and bob@b.com"
        result = redact_pii(text)
        assert "alice@a.com" not in result
        assert "bob@b.com" not in result
        assert result.count("[REDACTED_EMAIL]") == 2
