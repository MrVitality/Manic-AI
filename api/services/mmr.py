"""Maximal Marginal Relevance (MMR) for diverse search results.

Pure-Python implementation — no numpy dependency required.
"""

import math
from typing import List


def _dot(a: List[float], b: List[float]) -> float:
    """Dot product of two equal-length vectors."""
    return sum(x * y for x, y in zip(a, b))


def _norm(v: List[float]) -> float:
    """Euclidean norm of a vector."""
    return math.sqrt(sum(x * x for x in v))


def _normalize(v: List[float]) -> List[float]:
    """Return a unit-length copy of *v*. Returns the zero vector unchanged."""
    n = _norm(v)
    if n < 1e-10:
        return list(v)
    return [x / n for x in v]


def _cosine_sim(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two pre-normalised vectors."""
    return max(-1.0, min(1.0, _dot(a, b)))


def mmr_rerank(
    query_embedding: List[float],
    candidate_embeddings: List[List[float]],
    candidate_scores: List[float],
    k: int = 5,
    lambda_mult: float = 0.7,
) -> List[int]:
    """Re-rank candidates using MMR to balance relevance and diversity.

    MMR score = lambda_mult * relevance - (1 - lambda_mult) * max_sim_to_selected

    Args:
        query_embedding: The query vector.
        candidate_embeddings: List of candidate document vectors. Must be the
            same length as *candidate_scores*.
        candidate_scores: Original similarity scores (higher is more relevant).
        k: Number of results to return.
        lambda_mult: Trade-off weight. 0 = maximum diversity, 1 = maximum
            relevance. Defaults to 0.7 (favour relevance slightly).

    Returns:
        List of indices into the candidates list, ordered by MMR selection.
        The list length is min(k, len(candidate_embeddings)).
    """
    if not candidate_embeddings:
        return []

    n = len(candidate_embeddings)
    k = min(k, n)

    # Pre-normalise all vectors once to avoid repeated work inside the loop.
    norm_query = _normalize(query_embedding)
    norm_cands = [_normalize(emb) for emb in candidate_embeddings]

    selected: List[int] = []
    remaining: List[int] = list(range(n))

    for _ in range(k):
        best_idx = -1
        best_score = float("-inf")

        for idx in remaining:
            # Relevance: use the original retrieval score directly so that
            # hybrid / BM25 scores are respected without re-computing cosine.
            relevance = candidate_scores[idx]

            # Diversity: maximum cosine similarity to any already-selected doc.
            if selected:
                max_sim = max(
                    _cosine_sim(norm_cands[s], norm_cands[idx])
                    for s in selected
                )
            else:
                max_sim = 0.0

            mmr_score = lambda_mult * relevance - (1.0 - lambda_mult) * max_sim

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx

        if best_idx < 0:
            break

        selected.append(best_idx)
        remaining.remove(best_idx)

    return selected
