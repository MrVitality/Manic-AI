"""Tests for RAG evaluation metrics."""
import pytest

from api.services.rag_eval import (
    compute_eval_metrics,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    score_distribution,
)


class TestPrecisionAtK:
    def test_all_relevant(self):
        assert precision_at_k(["a", "b", "c"], ["a", "b", "c"], 3) == 1.0

    def test_none_relevant(self):
        assert precision_at_k(["a", "b", "c"], ["x", "y"], 3) == 0.0

    def test_partial(self):
        assert precision_at_k(["a", "b", "c"], ["a", "c"], 3) == pytest.approx(2 / 3)

    def test_k_larger_than_results(self):
        assert precision_at_k(["a"], ["a"], 5) == 1.0

    def test_empty_retrieved(self):
        assert precision_at_k([], ["a"], 3) == 0.0

    def test_k_truncates_list(self):
        # Only top-1 considered; "b" is relevant but beyond k
        assert precision_at_k(["a", "b"], ["b"], 1) == 0.0


class TestRecallAtK:
    def test_all_found(self):
        assert recall_at_k(["a", "b", "c"], ["a", "b"], 3) == 1.0

    def test_none_found(self):
        assert recall_at_k(["x", "y"], ["a", "b"], 2) == 0.0

    def test_partial(self):
        assert recall_at_k(["a", "x"], ["a", "b"], 2) == 0.5

    def test_empty_relevant(self):
        assert recall_at_k(["a"], [], 1) == 0.0

    def test_k_limits_window(self):
        # "b" is at index 2 but k=1, so not counted
        assert recall_at_k(["a", "b"], ["b"], 1) == 0.0


class TestMRR:
    def test_first_hit(self):
        assert mean_reciprocal_rank(["a", "b", "c"], ["a"]) == 1.0

    def test_second_hit(self):
        assert mean_reciprocal_rank(["x", "a", "c"], ["a"]) == pytest.approx(0.5)

    def test_third_hit(self):
        assert mean_reciprocal_rank(["x", "y", "a"], ["a"]) == pytest.approx(1 / 3)

    def test_no_hit(self):
        assert mean_reciprocal_rank(["x", "y", "z"], ["a"]) == 0.0

    def test_empty_retrieved(self):
        assert mean_reciprocal_rank([], ["a"]) == 0.0

    def test_multiple_relevant_returns_first(self):
        # "b" is at index 1, "a" is at index 2; MRR should be based on "b"
        assert mean_reciprocal_rank(["x", "b", "a"], ["a", "b"]) == pytest.approx(0.5)


class TestNDCG:
    def test_perfect_ranking(self):
        assert ndcg_at_k(["a", "b", "c"], ["a", "b", "c"], 3) == pytest.approx(1.0)

    def test_no_relevant(self):
        assert ndcg_at_k(["x", "y"], ["a", "b"], 2) == 0.0

    def test_partial_ranking(self):
        score = ndcg_at_k(["x", "a", "b"], ["a", "b"], 3)
        assert 0.0 < score < 1.0

    def test_empty_retrieved(self):
        assert ndcg_at_k([], ["a"], 5) == 0.0

    def test_empty_relevant(self):
        assert ndcg_at_k(["a", "b"], [], 2) == 0.0

    def test_single_relevant_at_top(self):
        assert ndcg_at_k(["a", "x", "y"], ["a"], 3) == pytest.approx(1.0)

    def test_single_relevant_not_at_top(self):
        # "a" is at rank 3; DCG = 1/log2(4); IDCG = 1/log2(2) = 1.0
        import math
        expected = (1.0 / math.log2(4)) / 1.0
        assert ndcg_at_k(["x", "y", "a"], ["a"], 3) == pytest.approx(expected)


class TestScoreDistribution:
    def test_empty(self):
        result = score_distribution([])
        assert result["min"] == 0.0
        assert result["max"] == 0.0
        assert result["mean"] == 0.0
        assert result["median"] == 0.0

    def test_single(self):
        result = score_distribution([0.5])
        assert result["min"] == 0.5
        assert result["max"] == 0.5
        assert result["mean"] == pytest.approx(0.5)
        assert result["median"] == 0.5

    def test_multiple(self):
        result = score_distribution([0.1, 0.5, 0.9])
        assert result["min"] == pytest.approx(0.1)
        assert result["max"] == pytest.approx(0.9)
        assert result["mean"] == pytest.approx(0.5)
        assert result["median"] == pytest.approx(0.5)

    def test_even_count_median(self):
        result = score_distribution([0.2, 0.4, 0.6, 0.8])
        assert result["median"] == pytest.approx(0.5)  # (0.4 + 0.6) / 2

    def test_unsorted_input(self):
        result = score_distribution([0.9, 0.1, 0.5])
        assert result["min"] == pytest.approx(0.1)
        assert result["max"] == pytest.approx(0.9)


class TestComputeEvalMetrics:
    def test_returns_all_metrics(self):
        metrics = compute_eval_metrics(["a", "b", "c"], ["a", "c"])
        assert "mrr" in metrics
        assert "precision@1" in metrics
        assert "precision@3" in metrics
        assert "recall@1" in metrics
        assert "recall@5" in metrics
        assert "ndcg@1" in metrics
        assert "ndcg@3" in metrics
        assert "total_retrieved" in metrics
        assert "total_relevant" in metrics

    def test_custom_k_values(self):
        metrics = compute_eval_metrics(["a", "b"], ["a"], k_values=[2, 4])
        assert "precision@2" in metrics
        assert "precision@4" in metrics
        assert "precision@1" not in metrics

    def test_perfect_result(self):
        metrics = compute_eval_metrics(["a", "b"], ["a", "b"], k_values=[2])
        assert metrics["precision@2"] == pytest.approx(1.0)
        assert metrics["recall@2"] == pytest.approx(1.0)
        assert metrics["ndcg@2"] == pytest.approx(1.0)
        assert metrics["mrr"] == pytest.approx(1.0)

    def test_no_relevant_found(self):
        metrics = compute_eval_metrics(["x", "y"], ["a", "b"], k_values=[2])
        assert metrics["mrr"] == 0.0
        assert metrics["precision@2"] == 0.0
        assert metrics["recall@2"] == 0.0
        assert metrics["ndcg@2"] == 0.0

    def test_counts_correct(self):
        metrics = compute_eval_metrics(["a", "b", "c"], ["a", "b"])
        assert metrics["total_retrieved"] == 3.0
        assert metrics["total_relevant"] == 2.0
