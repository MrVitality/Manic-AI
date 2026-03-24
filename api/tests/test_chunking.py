"""Tests for api.services.chunking — pure functions, no I/O needed."""


from api.services.chunking import (
    chunk_text,
    semantic_chunk_text,
    chunk_document,
    _split_by_markdown_headers,
    _split_into_paragraphs,
    _split_into_sentences,
    _estimate_tokens,
    _build_chunks_from_segments,
)


# ---------------------------------------------------------------------------
# Simple chunking (chunk_text)
# ---------------------------------------------------------------------------


class TestChunkText:
    def test_short_text_single_chunk(self):
        text = "Hello world."
        chunks = chunk_text(text, chunk_size=500)
        assert len(chunks) == 1
        assert chunks[0]["content"] == text
        assert chunks[0]["index"] == 0
        assert chunks[0]["start"] == 0

    def test_empty_text(self):
        chunks = chunk_text("", chunk_size=500)
        # empty or whitespace-collapsed string should produce one chunk (empty string)
        # or zero chunks depending on implementation
        assert len(chunks) <= 1

    def test_multiple_chunks_produced(self):
        text = "Word " * 200  # ~1000 chars
        chunks = chunk_text(text, chunk_size=100, overlap=10)
        assert len(chunks) > 1
        # All chunks have required keys
        for c in chunks:
            assert "content" in c
            assert "index" in c
            assert "start" in c
            assert "end" in c

    def test_overlap_clamped_when_too_large(self):
        """overlap >= chunk_size should be clamped to chunk_size - 1."""
        text = "A sentence. " * 50
        # Should not infinite loop
        chunks = chunk_text(text, chunk_size=50, overlap=50)
        assert len(chunks) >= 1

    def test_chunk_indices_sequential(self):
        text = "Sentence one. Sentence two. Sentence three. " * 20
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        indices = [c["index"] for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_normalizes_windows_newlines(self):
        text = "Line one.\r\nLine two.\r\nLine three."
        chunks = chunk_text(text, chunk_size=500)
        assert "\r" not in chunks[0]["content"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class TestMarkdownSplitter:
    def test_no_headers(self):
        sections = _split_by_markdown_headers("Just some plain text.")
        assert len(sections) == 1
        assert sections[0]["header"] == ""

    def test_single_header(self):
        text = "# Title\n\nBody paragraph."
        sections = _split_by_markdown_headers(text)
        assert any(s["header"].startswith("#") for s in sections)

    def test_multiple_headers(self):
        text = "# H1\nBody1\n## H2\nBody2\n### H3\nBody3"
        sections = _split_by_markdown_headers(text)
        headers = [s["header"] for s in sections if s["header"]]
        assert len(headers) == 3


class TestParagraphSplitter:
    def test_single_paragraph(self):
        assert _split_into_paragraphs("no breaks here") == ["no breaks here"]

    def test_double_newline(self):
        result = _split_into_paragraphs("Para one.\n\nPara two.")
        assert len(result) == 2


class TestSentenceSplitter:
    def test_simple_sentences(self):
        result = _split_into_sentences("First. Second. Third.")
        assert len(result) == 3

    def test_no_sentence_boundary(self):
        result = _split_into_sentences("No period here")
        assert len(result) == 1


class TestEstimateTokens:
    def test_basic(self):
        assert _estimate_tokens("abcd") == 1
        assert _estimate_tokens("a" * 100) == 25

    def test_empty(self):
        assert _estimate_tokens("") == 1  # max(1, 0)


class TestBuildChunksFromSegments:
    def test_single_segment_within_budget(self):
        result = _build_chunks_from_segments(["Hello world"], target_tokens=100)
        assert result == ["Hello world"]

    def test_splits_when_over_budget(self):
        segments = ["A" * 100, "B" * 100, "C" * 100]
        result = _build_chunks_from_segments(segments, target_tokens=30)
        assert len(result) >= 2


# ---------------------------------------------------------------------------
# Semantic chunking
# ---------------------------------------------------------------------------


class TestSemanticChunkText:
    def test_produces_chunks_with_parent_content(self):
        text = (
            "# Introduction\n\n"
            "First paragraph with enough text to be meaningful. "
            "It has multiple sentences. And a few more.\n\n"
            "## Details\n\n"
            "Second section with different content. "
            "More sentences follow here. And another one."
        )
        chunks = semantic_chunk_text(text, retrieval_token_size=50, context_token_size=200)
        assert len(chunks) >= 1
        for c in chunks:
            assert "content" in c
            assert "parent_content" in c
            assert "index" in c
            assert "header" in c

    def test_fallback_to_simple_on_empty(self):
        """If semantic splitting produces nothing, it falls back to simple chunking."""
        chunks = semantic_chunk_text("   ")
        # Should still return a list (possibly empty for whitespace-only)
        assert isinstance(chunks, list)


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------


class TestChunkDocument:
    def test_simple_strategy(self):
        text = "Some text to chunk. " * 50
        chunks = chunk_document(text, strategy="simple", chunk_size=100, chunk_overlap=10)
        assert len(chunks) >= 1
        assert "content" in chunks[0]

    def test_semantic_strategy(self):
        text = "# Header\n\nA paragraph. Another sentence.\n\n## Section\n\nMore text."
        chunks = chunk_document(text, strategy="semantic")
        assert len(chunks) >= 1
