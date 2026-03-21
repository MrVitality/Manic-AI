"""Tests for pure functions in repositories/supabase_documents.py."""

from api.repositories.supabase_documents import _parse_metadata


class TestParseMetadata:
    def test_valid_json(self):
        assert _parse_metadata('{"key": "value"}') == {"key": "value"}

    def test_none_returns_empty(self):
        assert _parse_metadata(None) == {}

    def test_empty_string_returns_empty(self):
        assert _parse_metadata("") == {}

    def test_invalid_json_returns_empty(self):
        assert _parse_metadata("{not valid json") == {}

    def test_non_string_type_returns_empty(self):
        assert _parse_metadata(42) == {}

    def test_nested_json(self):
        result = _parse_metadata('{"a": {"b": [1, 2, 3]}}')
        assert result == {"a": {"b": [1, 2, 3]}}
