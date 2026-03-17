"""Tests for Pydantic Settings validation in api.config."""

import pytest
from pydantic import ValidationError

from api.config import Settings


class TestSettingsDefaults:
    """Verify that Settings instantiates with valid defaults."""

    def test_default_values(self):
        s = Settings()
        assert s.OLLAMA_URL == "http://ollama:11434"
        assert s.EMBEDDING_MODEL == "nomic-embed-text"
        assert s.CHAT_MODEL == "llama3.2:3b"
        assert s.VECTOR_DIMENSION == 768
        assert s.RAG_TOP_K == 5
        assert 0.0 <= s.RAG_THRESHOLD <= 1.0
        assert 0.0 <= s.RAG_KEYWORD_WEIGHT <= 1.0
        assert s.RAG_CONTEXT_WINDOW == 4096

    def test_cors_origins_empty_falls_back_to_localhost(self):
        s = Settings(CORS_ORIGINS="")
        origins = s.parse_cors_origins()
        assert "http://localhost:3000" in origins
        assert "http://localhost:3006" in origins

    def test_cors_origins_parsed(self):
        s = Settings(CORS_ORIGINS="http://a.com, http://b.com")
        origins = s.parse_cors_origins()
        assert origins == ["http://a.com", "http://b.com"]


class TestSettingsValidation:
    """Verify that validators reject invalid values."""

    def test_vector_dimension_must_be_positive(self):
        with pytest.raises(ValidationError):
            Settings(VECTOR_DIMENSION=0)

    def test_vector_dimension_negative(self):
        with pytest.raises(ValidationError):
            Settings(VECTOR_DIMENSION=-1)

    def test_rag_top_k_must_be_positive(self):
        with pytest.raises(ValidationError):
            Settings(RAG_TOP_K=0)

    def test_rag_threshold_below_zero(self):
        with pytest.raises(ValidationError):
            Settings(RAG_THRESHOLD=-0.1)

    def test_rag_threshold_above_one(self):
        with pytest.raises(ValidationError):
            Settings(RAG_THRESHOLD=1.1)

    def test_keyword_weight_below_zero(self):
        with pytest.raises(ValidationError):
            Settings(RAG_KEYWORD_WEIGHT=-0.1)

    def test_keyword_weight_above_one(self):
        with pytest.raises(ValidationError):
            Settings(RAG_KEYWORD_WEIGHT=1.5)
