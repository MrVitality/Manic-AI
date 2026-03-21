"""Tests for cross-encoder scoring helpers in services/cross_encoder.py."""

from api.services.cross_encoder import _build_passages_text, _parse_scores


class TestBuildPassagesText:
    def test_single_chunk(self):
        result = _build_passages_text([{"content": "hello world"}])
        assert result == "1. hello world"

    def test_multiple_chunks_numbered(self):
        chunks = [{"content": "aaa"}, {"content": "bbb"}]
        result = _build_passages_text(chunks)
        assert result.startswith("1. aaa\n2. bbb")

    def test_content_truncated_at_500(self):
        chunk = {"content": "x" * 600}
        result = _build_passages_text([chunk])
        assert len(result.split(". ", 1)[1]) == 500

    def test_empty_list(self):
        assert _build_passages_text([]) == ""

    def test_missing_content_key(self):
        result = _build_passages_text([{"id": "no-content"}])
        assert result == "1. "


class TestParseScores:
    def test_clean_json_array(self):
        assert _parse_scores("[8, 3, 10, 1]", 4) == [8.0, 3.0, 10.0, 1.0]

    def test_values_clamped(self):
        result = _parse_scores("[15, -2]", 2)
        assert result == [10.0, 0.0]

    def test_markdown_fence_stripped(self):
        result = _parse_scores("```json\n[5, 7]\n```", 2)
        assert result == [5.0, 7.0]

    def test_pads_with_zeros(self):
        result = _parse_scores("[9]", 3)
        assert result == [9.0, 0.0, 0.0]

    def test_truncates_excess(self):
        result = _parse_scores("[1, 2, 3, 4, 5]", 3)
        assert result == [1.0, 2.0, 3.0]

    def test_fallback_number_extraction(self):
        result = _parse_scores("the scores are 7 and 4 respectively", 2)
        assert result == [7.0, 4.0]

    def test_unparseable_returns_zeros(self):
        result = _parse_scores("no numbers here at all", 3)
        assert result == [0.0, 0.0, 0.0]

    def test_float_scores(self):
        result = _parse_scores("[7.5, 3.2]", 2)
        assert result == [7.5, 3.2]

    def test_array_in_prose(self):
        result = _parse_scores("Here are the scores: [6, 8, 2] based on analysis", 3)
        assert result == [6.0, 8.0, 2.0]
