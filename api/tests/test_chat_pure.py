"""Tests for pure functions in services/chat.py."""

from api.services.chat import _build_citations, build_rag_prompt


class TestBuildRagPrompt:
    def test_no_context_returns_query(self):
        assert build_rag_prompt("What is AI?", []) == "What is AI?"

    def test_single_chunk_formatted(self):
        result = build_rag_prompt("Q?", [{"content": "context text"}])
        assert "[Source 1]: context text" in result
        assert "Question: Q?" in result
        assert "Answer:" in result

    def test_multiple_chunks_numbered(self):
        chunks = [{"content": "a"}, {"content": "b"}]
        result = build_rag_prompt("Q", chunks)
        assert "[Source 1]: a" in result
        assert "[Source 2]: b" in result

    def test_separator_present(self):
        chunks = [{"content": "a"}, {"content": "b"}]
        result = build_rag_prompt("Q", chunks)
        assert "---" in result


class TestBuildCitations:
    def test_builds_from_chunk(self):
        sources = [{"id": "c1", "document_id": "d1", "content": "hello", "score": 0.9, "metadata": {"start": 5}}]
        citations = _build_citations(sources)
        assert len(citations) == 1
        assert citations[0].source_id == "c1"
        assert citations[0].document_id == "d1"
        assert citations[0].score == 0.9
        assert citations[0].chunk_index == 5

    def test_content_preview_truncated(self):
        sources = [{"id": "c1", "document_id": "d1", "content": "x" * 500, "score": 0.5, "metadata": {}}]
        citations = _build_citations(sources)
        assert len(citations[0].content_preview) <= 200

    def test_metadata_non_dict_uses_zero(self):
        sources = [{"id": "c1", "document_id": "d1", "content": "hi", "score": 0.5, "metadata": "bad"}]
        citations = _build_citations(sources)
        assert citations[0].chunk_index == 0

    def test_empty_sources(self):
        assert _build_citations([]) == []

    def test_missing_keys_use_defaults(self):
        sources = [{"content": "text"}]
        citations = _build_citations(sources)
        assert len(citations) == 1
        assert citations[0].source_id == ""
        assert citations[0].document_id == ""
