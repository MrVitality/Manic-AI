"""Domain-specific Prometheus metrics for Manic AI."""
from prometheus_client import Counter, Histogram, Gauge

# RAG / Search
rag_queries_total = Counter(
    "rag_queries_total", "Total RAG queries",
    ["backend", "search_type", "cache_hit"]
)
search_latency_seconds = Histogram(
    "search_latency_seconds", "Search latency",
    ["backend"], buckets=[0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
)

# Embeddings
embedding_duration_seconds = Histogram(
    "embedding_duration_seconds", "Embedding generation latency",
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30]
)
embedding_cache_total = Counter(
    "embedding_cache_total", "Embedding cache hits/misses",
    ["result"]  # "hit" or "miss"
)

# LLM Inference
llm_completion_duration_seconds = Histogram(
    "llm_completion_duration_seconds", "LLM completion latency",
    ["model", "backend"], buckets=[0.5, 1, 2, 5, 10, 30, 60, 120]
)
llm_tokens_total = Counter(
    "llm_tokens_total", "LLM tokens used",
    ["model", "type"]  # type: "prompt" or "completion"
)

# Ingestion
ingest_documents_total = Counter(
    "ingest_documents_total", "Documents ingested",
    ["status"]  # "success", "failed", "partial"
)
ingest_chunks_total = Counter(
    "ingest_chunks_total", "Chunks created during ingestion"
)
