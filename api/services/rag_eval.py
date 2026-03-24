"""RAG evaluation metrics — precision, recall, MRR, NDCG."""
from typing import Dict, List
import math


def precision_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float:
    """Fraction of top-k retrieved docs that are relevant."""
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    relevant_set = set(relevant_ids)
    hits = sum(1 for doc_id in top_k if doc_id in relevant_set)
    return hits / len(top_k)


def recall_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float:
    """Fraction of relevant docs found in top-k results."""
    if not relevant_ids:
        return 0.0
    top_k = set(retrieved_ids[:k])
    hits = sum(1 for doc_id in relevant_ids if doc_id in top_k)
    return hits / len(relevant_ids)


def mean_reciprocal_rank(retrieved_ids: List[str], relevant_ids: List[str]) -> float:
    """1/rank of the first relevant result. 0 if none found."""
    relevant_set = set(relevant_ids)
    for i, doc_id in enumerate(retrieved_ids):
        if doc_id in relevant_set:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float:
    """Normalized Discounted Cumulative Gain at k."""
    relevant_set = set(relevant_ids)
    top_k = retrieved_ids[:k]

    # DCG
    dcg = sum(
        1.0 / math.log2(i + 2)  # i+2 because log2(1)=0
        for i, doc_id in enumerate(top_k)
        if doc_id in relevant_set
    )

    # Ideal DCG (all relevant docs at top)
    ideal_count = min(len(relevant_ids), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_count))

    return dcg / idcg if idcg > 0 else 0.0


def compute_eval_metrics(
    retrieved_ids: List[str],
    relevant_ids: List[str],
    k_values: List[int] = [1, 3, 5, 10],
) -> Dict[str, float]:
    """Compute all metrics at multiple k values."""
    metrics: Dict[str, float] = {
        "mrr": mean_reciprocal_rank(retrieved_ids, relevant_ids),
        "total_retrieved": float(len(retrieved_ids)),
        "total_relevant": float(len(relevant_ids)),
    }
    for k in k_values:
        metrics[f"precision@{k}"] = precision_at_k(retrieved_ids, relevant_ids, k)
        metrics[f"recall@{k}"] = recall_at_k(retrieved_ids, relevant_ids, k)
        metrics[f"ndcg@{k}"] = ndcg_at_k(retrieved_ids, relevant_ids, k)
    return metrics


def score_distribution(scores: List[float]) -> Dict[str, float]:
    """Compute min/max/mean/median of a score list."""
    if not scores:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "median": 0.0}
    sorted_scores = sorted(scores)
    n = len(sorted_scores)
    return {
        "min": sorted_scores[0],
        "max": sorted_scores[-1],
        "mean": sum(sorted_scores) / n,
        "median": (
            sorted_scores[n // 2]
            if n % 2
            else (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2
        ),
    }
