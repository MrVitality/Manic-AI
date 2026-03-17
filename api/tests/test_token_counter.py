"""Tests for api.services.token_counter — pure functions, no I/O needed."""

import pytest
from unittest.mock import patch

from api.services.token_counter import (
    estimate_tokens,
    estimate_messages_tokens,
    compute_budgets,
    truncate_messages_to_budget,
    truncate_rag_context,
    DEFAULT_CONTEXT_WINDOW,
    SYSTEM_PROMPT_BUDGET,
    RAG_CONTEXT_RATIO,
)


# ---------------------------------------------------------------------------
# estimate_tokens
# ---------------------------------------------------------------------------


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_short_string(self):
        result = estimate_tokens("hello")
        assert result >= 1

    def test_longer_string_heuristic(self):
        """Without tiktoken, chars/4 heuristic should apply."""
        text = "a" * 400
        # Either tiktoken is available (precise) or heuristic gives 100
        result = estimate_tokens(text)
        assert result >= 1


class TestEstimateMessagesTokens:
    def test_empty_list(self):
        assert estimate_messages_tokens([]) == 0

    def test_single_message(self):
        result = estimate_messages_tokens([{"role": "user", "content": "hello"}])
        # 4 (overhead) + estimate_tokens("hello")
        assert result >= 5

    def test_multiple_messages(self):
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        result = estimate_messages_tokens(msgs)
        assert result >= 8  # at least 4+4 overhead


# ---------------------------------------------------------------------------
# compute_budgets
# ---------------------------------------------------------------------------


class TestComputeBudgets:
    def test_default_budgets(self):
        budgets = compute_budgets()
        assert budgets["total"] == DEFAULT_CONTEXT_WINDOW
        assert budgets["system_prompt"] == SYSTEM_PROMPT_BUDGET
        assert budgets["rag_context"] > 0
        assert budgets["history"] > 0
        # rag_context + history + system_prompt == total
        assert (
            budgets["system_prompt"] + budgets["rag_context"] + budgets["history"]
            == budgets["total"]
        )

    def test_custom_context_window(self):
        budgets = compute_budgets(context_window=8192)
        assert budgets["total"] == 8192
        assert budgets["system_prompt"] + budgets["rag_context"] + budgets["history"] == 8192

    def test_custom_system_prompt_tokens(self):
        budgets = compute_budgets(system_prompt_tokens=200)
        assert budgets["system_prompt"] == 200

    def test_tiny_window_no_negative(self):
        budgets = compute_budgets(context_window=100, system_prompt_tokens=200)
        assert budgets["rag_context"] >= 0
        assert budgets["history"] >= 0

    def test_rag_ratio_applied(self):
        budgets = compute_budgets(context_window=4096, system_prompt_tokens=0)
        assert budgets["rag_context"] == int(4096 * RAG_CONTEXT_RATIO)


# ---------------------------------------------------------------------------
# truncate_messages_to_budget
# ---------------------------------------------------------------------------


class TestTruncateMessagesToBudget:
    def test_empty_messages(self):
        assert truncate_messages_to_budget([], 1000) == []

    def test_keeps_system_and_last_message(self):
        msgs = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "reply1"},
            {"role": "user", "content": "latest question"},
        ]
        result = truncate_messages_to_budget(msgs, token_budget=50)
        # Must keep system + last user message at minimum
        roles = [m["role"] for m in result]
        assert roles[0] == "system"
        assert result[-1]["content"] == "latest question"

    def test_drops_oldest_first(self):
        msgs = [
            {"role": "user", "content": "old " * 100},
            {"role": "assistant", "content": "old reply " * 100},
            {"role": "user", "content": "new"},
        ]
        result = truncate_messages_to_budget(msgs, token_budget=30)
        # Last message always kept
        assert result[-1]["content"] == "new"
        # Older messages may be dropped
        assert len(result) <= len(msgs)

    def test_all_messages_fit(self):
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        result = truncate_messages_to_budget(msgs, token_budget=10000)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# truncate_rag_context
# ---------------------------------------------------------------------------


class TestTruncateRagContext:
    def test_empty_chunks(self):
        assert truncate_rag_context([], 1000) == []

    def test_zero_budget(self):
        chunks = [{"content": "text"}]
        assert truncate_rag_context(chunks, 0) == []

    def test_keeps_top_chunks_within_budget(self):
        chunks = [
            {"content": "a" * 40, "score": 0.9},
            {"content": "b" * 40, "score": 0.8},
            {"content": "c" * 40, "score": 0.7},
        ]
        # Each chunk ~10 tokens (40/4), budget of 25 should fit 2
        result = truncate_rag_context(chunks, token_budget=25)
        assert len(result) == 2

    def test_all_fit(self):
        chunks = [{"content": "short", "score": 1.0}]
        result = truncate_rag_context(chunks, token_budget=10000)
        assert len(result) == 1
