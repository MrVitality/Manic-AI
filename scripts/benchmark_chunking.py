#!/usr/bin/env python3
"""Benchmark chunking strategies for RAG quality.

Runs both 'simple' and 'semantic' chunking strategies across a parameter grid,
measuring chunk count, avg/min/max size, coverage, and wall-clock time.
Optionally runs a retrieval-quality simulation using the rag_eval metrics when
a query set is provided.

Usage:
    python scripts/benchmark_chunking.py
    python scripts/benchmark_chunking.py --file path/to/document.md
    python scripts/benchmark_chunking.py --file doc.md --queries queries.txt
    python scripts/benchmark_chunking.py --json          # machine-readable output
    python scripts/benchmark_chunking.py --top 3         # show top N configs per metric
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Project root on sys.path so api.* imports resolve when run from any cwd
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from api.services.chunking import chunk_document
from api.services.rag_eval import compute_eval_metrics

# ---------------------------------------------------------------------------
# Parameter grids
# ---------------------------------------------------------------------------

SIMPLE_CONFIGS: List[Dict[str, int]] = [
    {"chunk_size": 200, "chunk_overlap": 20},
    {"chunk_size": 500, "chunk_overlap": 50},
    {"chunk_size": 500, "chunk_overlap": 100},
    {"chunk_size": 1000, "chunk_overlap": 100},
    {"chunk_size": 1000, "chunk_overlap": 200},
    {"chunk_size": 2000, "chunk_overlap": 200},
]

SEMANTIC_CONFIGS: List[Dict[str, int]] = [
    {"retrieval_token_size": 100, "context_token_size": 500},
    {"retrieval_token_size": 150, "context_token_size": 750},
    {"retrieval_token_size": 200, "context_token_size": 1000},
    {"retrieval_token_size": 300, "context_token_size": 1500},
    {"retrieval_token_size": 400, "context_token_size": 2000},
]

# ---------------------------------------------------------------------------
# Built-in synthetic document (~2000 words, markdown with headers/code/lists)
# ---------------------------------------------------------------------------

SYNTHETIC_DOCUMENT = """\
# Introduction to Machine Learning

Machine learning is a transformative branch of artificial intelligence that enables
computers to learn from data and improve their performance on tasks without being
explicitly programmed for each step. Rather than following hand-crafted rules,
machine learning systems identify patterns, make decisions, and adapt their
behaviour as they are exposed to more data over time.

The field has exploded in relevance over the past decade, powered by three
converging forces: vastly larger datasets, dramatically cheaper compute, and
algorithmic advances that allow models to extract useful structure from raw
information. Today, machine learning underpins recommendation engines, autonomous
vehicles, medical diagnosis, natural language processing, and countless other
applications that shape daily life.

## Core Concepts

### Supervised Learning

Supervised learning is the most widely used family of machine learning techniques.
In supervised learning, every training example consists of an input (a feature
vector) paired with a desired output (a label). The model learns a mapping from
inputs to outputs by minimising a loss function that measures the gap between its
predictions and the ground-truth labels.

Common supervised tasks include:

- **Classification** — assigning inputs to discrete categories (e.g., spam vs.
  not spam, image of cat vs. dog).
- **Regression** — predicting a continuous numerical value (e.g., house price,
  stock return, temperature forecast).
- **Structured prediction** — outputting complex structures such as sequences,
  trees, or graphs (e.g., machine translation, dependency parsing).

Popular supervised algorithms include linear regression, logistic regression,
decision trees, random forests, gradient boosted trees (XGBoost, LightGBM), and
deep neural networks. The right choice depends on dataset size, feature
cardinality, interpretability requirements, and available compute.

### Unsupervised Learning

Unsupervised learning operates on unlabelled data, seeking to discover hidden
structure without explicit feedback. Because labels are expensive to acquire,
unsupervised methods are crucial for leveraging the vast quantities of raw data
available in the wild.

Key unsupervised techniques include:

- **Clustering** — grouping examples by similarity. K-means and DBSCAN are classic
  approaches; hierarchical clustering builds a tree of nested groups.
- **Dimensionality reduction** — projecting high-dimensional data into fewer
  dimensions while preserving structure. PCA finds linear projections; t-SNE and
  UMAP find non-linear embeddings suited for visualisation.
- **Generative modelling** — learning the underlying data distribution to generate
  new, realistic samples. Variational autoencoders (VAEs) and generative adversarial
  networks (GANs) are prominent examples.

### Reinforcement Learning

Reinforcement learning (RL) trains an *agent* to take actions in an *environment*
in order to maximise cumulative *reward*. Unlike supervised learning, there is no
labelled dataset; instead, the agent must explore the environment and learn from
the consequences of its own actions.

RL has produced landmark achievements such as superhuman Go play (AlphaGo),
professional-level video game agents (OpenAI Five, AlphaStar), and robot
locomotion. Modern large language models also use RL from human feedback (RLHF) to
align model outputs with human preferences.

## Neural Networks and Deep Learning

Artificial neural networks are loosely inspired by biological neurons. A network
is organised into layers of *units*, each computing a weighted sum of its inputs
followed by a non-linear *activation function* such as ReLU, sigmoid, or tanh.
Deep learning refers to networks with many layers (depth), enabling them to learn
hierarchical representations directly from raw inputs.

### Convolutional Neural Networks

Convolutional neural networks (CNNs) are the backbone of computer vision. Instead
of fully connected layers, they apply learned *filters* (kernels) that slide
across the input, making them translation-equivariant and dramatically reducing
parameter count compared to dense layers.

A typical CNN pipeline:

```python
import torch.nn as nn

model = nn.Sequential(
    nn.Conv2d(3, 32, kernel_size=3, padding=1),  # 32 filters, 3x3
    nn.ReLU(),
    nn.MaxPool2d(2),                              # halve spatial dims
    nn.Conv2d(32, 64, kernel_size=3, padding=1),
    nn.ReLU(),
    nn.AdaptiveAvgPool2d(1),                      # global average pool
    nn.Flatten(),
    nn.Linear(64, 10),                            # 10-class output
)
```

### Transformers

Transformers, introduced in "Attention Is All You Need" (Vaswani et al., 2017),
replaced recurrent architectures for sequence modelling. The key innovation is
*self-attention*: each token attends to every other token in the sequence,
allowing the model to capture long-range dependencies in a single layer.

The scaled dot-product attention mechanism is defined as:

```
Attention(Q, K, V) = softmax(QK^T / sqrt(d_k)) V
```

Where Q, K, V are queries, keys, and values derived from linear projections of
the input, and d_k is the key dimension used for scaling. Multi-head attention
runs several attention operations in parallel and concatenates the results,
allowing the model to focus on different aspects of the input simultaneously.

Large language models (LLMs) such as GPT-4, Claude, and Gemini are decoder-only
transformers trained on massive text corpora with a next-token prediction
objective. Fine-tuning and prompting techniques unlock capabilities ranging from
code generation to scientific reasoning.

## Training and Optimisation

### Gradient Descent

Almost all modern machine learning optimises parameters by gradient descent:
compute the gradient of the loss with respect to parameters, then take a small
step in the opposite direction. Stochastic gradient descent (SGD) approximates
the true gradient using a random *mini-batch* of examples, enabling training on
datasets far too large to fit in memory.

Common optimisers and their characteristics:

| Optimiser | Adaptive LR | Momentum | Notes |
|-----------|-------------|----------|-------|
| SGD       | No          | Optional | Simple, good for convex problems |
| AdaGrad   | Yes         | No       | Shrinks LR for frequent features |
| RMSProp   | Yes         | No       | Popular for RNNs |
| Adam      | Yes         | Yes      | Default choice for most deep learning |
| AdamW     | Yes         | Yes      | Adam + decoupled weight decay |

### Regularisation

Overfitting — memorising training data at the expense of generalisation — is the
central challenge in machine learning. Standard regularisation techniques include:

- **L2 regularisation (weight decay)** — adds a penalty proportional to the
  squared magnitude of weights, shrinking them toward zero.
- **Dropout** — randomly zeros activations during training, forcing the network to
  learn redundant representations.
- **Early stopping** — halt training when validation loss stops improving.
- **Data augmentation** — artificially expand the training set via transformations
  (crops, flips, colour jitter, mixup) that preserve labels.

### Learning Rate Scheduling

The learning rate is the single most important hyperparameter. Too large and
training diverges; too small and convergence is glacially slow. Common schedules:

```python
from torch.optim.lr_scheduler import CosineAnnealingLR, OneCycleLR

# Cosine annealing: smoothly decay LR to near zero
scheduler = CosineAnnealingLR(optimizer, T_max=num_epochs)

# 1-cycle policy: warm up then anneal (often fastest to converge)
scheduler = OneCycleLR(
    optimizer,
    max_lr=1e-3,
    steps_per_epoch=len(train_loader),
    epochs=num_epochs,
)
```

## Retrieval-Augmented Generation

Retrieval-Augmented Generation (RAG) combines the parametric knowledge stored in
a large language model with non-parametric retrieval from an external corpus. At
inference time the system:

1. Encodes the user query into a dense vector using an embedding model.
2. Retrieves the top-k most similar document chunks from a vector database
   (e.g., Qdrant, Pinecone, Supabase pgvector).
3. Concatenates the retrieved chunks with the original query as context.
4. Passes the augmented prompt to the LLM, which generates a grounded response.

RAG dramatically reduces hallucination and allows models to answer questions about
knowledge not present in their training data — including private documents, recent
events, and domain-specific corpora.

### Chunking Strategy

How a document is split into chunks fundamentally affects retrieval quality.
Chunks that are too large dilute relevance signals; chunks that are too small lose
context necessary for coherent answers.

The two main families of chunking strategies are:

- **Fixed-size / character-based** — split every N characters with an optional
  overlap. Simple and fast, but may cut sentences mid-thought.
- **Semantic / structure-aware** — respect natural boundaries such as markdown
  headers, paragraphs, and sentence endings. Produces more coherent chunks at the
  cost of variable size and higher complexity.

Parent-child chunking is a hybrid: small *retrieval* chunks are returned by
similarity search, but the LLM receives the larger *parent* chunk for context,
balancing precision in retrieval with coherence in generation.

## Evaluation and Metrics

Rigorous evaluation is non-negotiable for production ML systems. Key metrics:

- **Precision@k** — of the top-k retrieved results, what fraction are relevant?
- **Recall@k** — of all relevant results, what fraction appear in the top-k?
- **Mean Reciprocal Rank (MRR)** — average of the reciprocal rank of the first
  relevant result across queries.
- **NDCG@k** — Normalised Discounted Cumulative Gain; rewards relevant results
  that appear higher in the ranking.

Offline evaluation against a labelled query set is a prerequisite before any
retrieval system reaches production. A/B testing with real users then validates
that offline gains translate to user-observable improvements.

## Conclusion

Machine learning has evolved from a niche academic discipline into a foundational
technology that touches virtually every domain of human endeavour. Mastering the
core concepts — supervised, unsupervised, and reinforcement learning; neural
architectures; optimisation and regularisation; evaluation methodology — provides
the foundation needed to apply these tools responsibly and effectively.

The field continues to advance at a remarkable pace. Staying current requires
combining first-principles understanding with hands-on experimentation, critical
reading of the literature, and engagement with open-source tooling. The
benchmarking mindset that quantifies trade-offs before committing to a design is
as important as any individual algorithm.
"""

# ---------------------------------------------------------------------------
# Sample query set for retrieval simulation (used when no external queries given)
# ---------------------------------------------------------------------------

SAMPLE_QUERIES = [
    "What is supervised learning?",
    "How does self-attention work in transformers?",
    "What are common regularisation techniques?",
    "Explain the RAG pipeline",
    "What is the Adam optimiser?",
    "How do convolutional neural networks process images?",
    "What is the difference between precision and recall?",
    "What is parent-child chunking?",
]

# ---------------------------------------------------------------------------
# Benchmarking helpers
# ---------------------------------------------------------------------------


def benchmark_config(text: str, strategy: str, **kwargs: Any) -> Dict[str, Any]:
    """Run a single chunking configuration and collect statistics."""
    start = time.perf_counter()
    chunks = chunk_document(text, strategy=strategy, **kwargs)
    elapsed_ms = (time.perf_counter() - start) * 1000

    sizes = [len(c["content"]) for c in chunks]
    total_chars = sum(sizes)

    return {
        "strategy": strategy,
        "params": dict(kwargs),
        "chunk_count": len(chunks),
        "avg_size_chars": total_chars / len(sizes) if sizes else 0.0,
        "min_size": min(sizes) if sizes else 0,
        "max_size": max(sizes) if sizes else 0,
        "total_chars": total_chars,
        "coverage_pct": total_chars / len(text) * 100 if text else 0.0,
        "time_ms": round(elapsed_ms, 2),
        "has_parent_content": any("parent_content" in c for c in chunks),
        "unique_headers": len({c.get("header", "") for c in chunks if c.get("header")}),
        "chunks": chunks,  # kept for retrieval simulation; stripped before JSON output
    }


# ---------------------------------------------------------------------------
# Retrieval simulation (keyword overlap as a proxy for embedding similarity)
# ---------------------------------------------------------------------------


def _keyword_overlap_score(query: str, chunk_text: str) -> float:
    """Simple keyword overlap score (0-1) used as a retrieval proxy."""
    q_words = set(query.lower().split())
    c_words = set(chunk_text.lower().split())
    if not q_words:
        return 0.0
    return len(q_words & c_words) / len(q_words)


def simulate_retrieval(
    chunks: List[Dict],
    queries: List[str],
    k: int = 5,
) -> Dict[str, float]:
    """Simulate retrieval using keyword overlap and compute RAG eval metrics.

    This is a heuristic proxy — real retrieval uses dense embeddings.  The
    simulation is useful for comparing chunking configs against each other on
    the same document/query set without requiring a live vector store.
    """
    all_precision: List[float] = []
    all_recall: List[float] = []
    all_mrr: List[float] = []
    all_ndcg: List[float] = []

    chunk_ids = [str(i) for i in range(len(chunks))]

    for query in queries:
        # Score every chunk
        scored = [
            (str(i), _keyword_overlap_score(query, c["content"]))
            for i, c in enumerate(chunks)
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        retrieved_ids = [cid for cid, _ in scored]

        # "Relevant" = top 20% by score (at least 1)
        top_score = scored[0][1] if scored else 0.0
        if top_score == 0.0:
            continue
        threshold = top_score * 0.5
        relevant_ids = [cid for cid, score in scored if score >= threshold]

        metrics = compute_eval_metrics(retrieved_ids, relevant_ids, k_values=[k])
        all_precision.append(metrics[f"precision@{k}"])
        all_recall.append(metrics[f"recall@{k}"])
        all_mrr.append(metrics["mrr"])
        all_ndcg.append(metrics[f"ndcg@{k}"])

    def _mean(lst: List[float]) -> float:
        return sum(lst) / len(lst) if lst else 0.0

    return {
        f"mean_precision@{k}": round(_mean(all_precision), 4),
        f"mean_recall@{k}": round(_mean(all_recall), 4),
        "mean_mrr": round(_mean(all_mrr), 4),
        f"mean_ndcg@{k}": round(_mean(all_ndcg), 4),
    }


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

_COL = 80


def _hr(char: str = "-") -> str:
    return char * _COL


def _label(result: Dict) -> str:
    p = result["params"]
    if result["strategy"] == "simple":
        return f"simple  size={p['chunk_size']:>4}  overlap={p['chunk_overlap']:>3}"
    return f"semantic  retrieval={p['retrieval_token_size']:>3}  context={p['context_token_size']:>4}"


def _print_row(result: Dict, eval_metrics: Optional[Dict] = None) -> None:
    label = _label(result)
    base = (
        f"  {label}  →  "
        f"{result['chunk_count']:>3} chunks  "
        f"avg={result['avg_size_chars']:>6.0f}c  "
        f"[{result['min_size']:>4}–{result['max_size']:>5}]  "
        f"cov={result['coverage_pct']:>4.0f}%  "
        f"{result['time_ms']:>7.2f}ms"
    )
    if eval_metrics:
        k_key = [k for k in eval_metrics if k.startswith("mean_precision")][0]
        k = k_key.split("@")[1]
        base += (
            f"  P@{k}={eval_metrics[k_key]:.3f}"
            f"  R@{k}={eval_metrics[f'mean_recall@{k}']:.3f}"
            f"  MRR={eval_metrics['mean_mrr']:.3f}"
        )
    print(base)


def _print_summary(results: List[Dict], eval_results: Dict[int, Dict], top_n: int) -> None:
    print()
    print("=" * _COL)
    print("SUMMARY")
    print("=" * _COL)

    print(f"\n  Fastest configs (lowest time_ms):")
    by_speed = sorted(results, key=lambda r: r["time_ms"])
    for r in by_speed[:top_n]:
        print(f"    [{r['time_ms']:>7.2f}ms]  {_label(r)}  ({r['chunk_count']} chunks)")

    print(f"\n  Smallest avg chunk (most granular):")
    by_small = sorted(results, key=lambda r: r["avg_size_chars"])
    for r in by_small[:top_n]:
        print(f"    [avg {r['avg_size_chars']:>5.0f}c]  {_label(r)}  ({r['chunk_count']} chunks)")

    print(f"\n  Largest avg chunk (most contextual):")
    by_large = sorted(results, key=lambda r: r["avg_size_chars"], reverse=True)
    for r in by_large[:top_n]:
        print(f"    [avg {r['avg_size_chars']:>5.0f}c]  {_label(r)}  ({r['chunk_count']} chunks)")

    print(f"\n  Best coverage:")
    by_cov = sorted(results, key=lambda r: r["coverage_pct"], reverse=True)
    for r in by_cov[:top_n]:
        print(f"    [{r['coverage_pct']:>4.0f}%]  {_label(r)}")

    if eval_results:
        k_key = next(
            (k for k in next(iter(eval_results.values())) if k.startswith("mean_mrr")), None
        )
        if k_key:
            print(f"\n  Best MRR (retrieval quality proxy):")
            ranked = sorted(
                eval_results.items(), key=lambda item: item[1].get("mean_mrr", 0), reverse=True
            )
            for idx, metrics in ranked[:top_n]:
                r = results[idx]
                print(
                    f"    [MRR={metrics['mean_mrr']:.3f}]  {_label(r)}  "
                    f"({r['chunk_count']} chunks)"
                )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark RAG chunking strategies (simple vs semantic)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--file",
        metavar="PATH",
        help="Path to a text/markdown document to chunk (default: built-in synthetic doc)",
    )
    parser.add_argument(
        "--queries",
        metavar="PATH",
        help=(
            "Path to a newline-delimited query file for retrieval simulation. "
            "If omitted, uses built-in sample queries."
        ),
    )
    parser.add_argument(
        "--no-eval",
        action="store_true",
        help="Skip retrieval simulation (pure chunking benchmark only)",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=5,
        metavar="K",
        help="k value for precision@k / recall@k / NDCG@k (default: 5)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=3,
        metavar="N",
        help="Number of top configs to show in summary (default: 3)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON (machine-readable, suppresses table output)",
    )
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Load document
    # ------------------------------------------------------------------
    if args.file:
        doc_path = Path(args.file)
        if not doc_path.exists():
            print(f"ERROR: file not found: {doc_path}", file=sys.stderr)
            sys.exit(1)
        text = doc_path.read_text(encoding="utf-8")
        doc_label = str(doc_path)
    else:
        text = SYNTHETIC_DOCUMENT
        doc_label = "<built-in synthetic document>"

    # ------------------------------------------------------------------
    # Load queries
    # ------------------------------------------------------------------
    if args.queries:
        q_path = Path(args.queries)
        if not q_path.exists():
            print(f"ERROR: query file not found: {q_path}", file=sys.stderr)
            sys.exit(1)
        queries = [line.strip() for line in q_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        queries = SAMPLE_QUERIES

    run_eval = not args.no_eval

    if not args.json:
        print(_hr("="))
        print("RAG CHUNKING STRATEGY BENCHMARK")
        print(_hr("="))
        print(f"  Document : {doc_label}")
        print(f"  Length   : {len(text):,} chars  ({len(text.split()):,} words)")
        print(f"  Queries  : {len(queries)} ({'built-in' if not args.queries else args.queries})")
        print(f"  Eval     : {'yes (keyword-overlap proxy)' if run_eval else 'no'}")
        if run_eval:
            print(f"  k        : {args.k}")
        print()

    # ------------------------------------------------------------------
    # Run benchmarks
    # ------------------------------------------------------------------
    all_results: List[Dict] = []
    eval_results: Dict[int, Dict] = {}

    # --- Simple strategy ---
    if not args.json:
        print("SIMPLE STRATEGY")
        print(_hr())

    for cfg in SIMPLE_CONFIGS:
        result = benchmark_config(text, "simple", **cfg)
        chunks = result.pop("chunks")
        all_results.append(result)

        ev: Optional[Dict] = None
        if run_eval:
            ev = simulate_retrieval(chunks, queries, k=args.k)
            eval_results[len(all_results) - 1] = ev

        if not args.json:
            _print_row(result, ev)

    if not args.json:
        print()
        print("SEMANTIC STRATEGY")
        print(_hr())

    # --- Semantic strategy ---
    for cfg in SEMANTIC_CONFIGS:
        result = benchmark_config(text, "semantic", **cfg)
        chunks = result.pop("chunks")
        all_results.append(result)

        ev = None
        if run_eval:
            ev = simulate_retrieval(chunks, queries, k=args.k)
            eval_results[len(all_results) - 1] = ev

        if not args.json:
            _print_row(result, ev)

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------
    if args.json:
        output = []
        for i, r in enumerate(all_results):
            row = dict(r)
            if i in eval_results:
                row["eval"] = eval_results[i]
            output.append(row)
        print(json.dumps(output, indent=2))
        return

    _print_summary(all_results, eval_results, top_n=args.top)
    print()


if __name__ == "__main__":
    main()
