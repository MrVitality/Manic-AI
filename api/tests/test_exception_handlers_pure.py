"""Tests for pure functions in exception_handlers.py."""

import pytest

from api.exception_handlers import _code_for_status


class TestCodeForStatus:
    @pytest.mark.parametrize(
        "status,expected",
        [
            (400, "bad_request"),
            (401, "unauthorized"),
            (403, "forbidden"),
            (404, "not_found"),
            (409, "conflict"),
            (422, "validation_error"),
            (429, "rate_limit_exceeded"),
            (500, "internal_error"),
            (502, "bad_gateway"),
            (503, "service_unavailable"),
        ],
    )
    def test_mapped_codes(self, status, expected):
        assert _code_for_status(status) == expected

    def test_unknown_returns_internal_error(self):
        assert _code_for_status(418) == "internal_error"
        assert _code_for_status(999) == "internal_error"
