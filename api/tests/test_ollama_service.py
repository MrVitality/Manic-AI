"""Tests for model name validation in services/ollama.py."""

import pytest

from api.services.ollama import validate_model_name


class TestValidateModelName:
    def test_valid_simple_name(self):
        assert validate_model_name("llama3.2:3b") == "llama3.2:3b"

    def test_valid_with_allowed_chars(self):
        assert validate_model_name("my-model_v1.2:latest") == "my-model_v1.2:latest"

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            validate_model_name("")

    def test_slash_raises(self):
        with pytest.raises(ValueError):
            validate_model_name("../../etc/passwd")

    def test_over_200_raises(self):
        with pytest.raises(ValueError):
            validate_model_name("a" * 201)

    def test_exactly_200_accepted(self):
        assert validate_model_name("a" * 200) == "a" * 200

    def test_space_raises(self):
        with pytest.raises(ValueError):
            validate_model_name("model name")

    def test_semicolon_raises(self):
        with pytest.raises(ValueError):
            validate_model_name("model;drop")
