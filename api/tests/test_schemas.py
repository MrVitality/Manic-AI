"""Tests for Pydantic schema validation."""

import pytest
from pydantic import ValidationError

from api.schemas.chat import ChatMessage
from api.schemas.ingest import IngestRequest


class TestChatMessageSchema:
    def test_valid_roles(self):
        for role in ("system", "user", "assistant"):
            msg = ChatMessage(role=role, content="hello")
            assert msg.role == role

    def test_invalid_role_raises(self):
        with pytest.raises(ValidationError):
            ChatMessage(role="admin", content="hello")

    def test_content_max_length_exceeded(self):
        with pytest.raises(ValidationError):
            ChatMessage(role="user", content="x" * 100_001)

    def test_content_at_max_accepted(self):
        msg = ChatMessage(role="user", content="x" * 100_000)
        assert len(msg.content) == 100_000


class TestIngestRequestValidator:
    def test_valid_overlap(self):
        req = IngestRequest(content="text", filename="f.txt", chunk_size=500, chunk_overlap=100)
        assert req.chunk_overlap == 100

    def test_overlap_equal_raises(self):
        with pytest.raises(ValidationError):
            IngestRequest(content="text", filename="f.txt", chunk_size=100, chunk_overlap=100)

    def test_overlap_greater_raises(self):
        with pytest.raises(ValidationError):
            IngestRequest(content="text", filename="f.txt", chunk_size=100, chunk_overlap=200)

    def test_semantic_skips_overlap_check(self):
        req = IngestRequest(
            content="text", filename="f.txt",
            chunk_size=100, chunk_overlap=100,
            chunking_strategy="semantic",
        )
        assert req.chunking_strategy == "semantic"

    def test_chunk_size_min(self):
        with pytest.raises(ValidationError):
            IngestRequest(content="text", filename="f.txt", chunk_size=0)

    def test_backend_literal(self):
        with pytest.raises(ValidationError):
            IngestRequest(content="text", filename="f.txt", backend="invalid")
