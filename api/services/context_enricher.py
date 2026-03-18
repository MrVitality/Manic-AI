"""Contextual chunk enrichment for improved RAG retrieval.

At ingest time, each chunk is enriched with a one-sentence contextual
summary that explains where the chunk fits within the larger document.
This helps the embedding model produce more informative vectors.

Reference: Anthropic's "Contextual Retrieval" technique.
"""

import asyncio
import json
import logging
from typing import Dict, List

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

# Maximum concurrent enrichment requests to avoid overwhelming Ollama
_ENRICHMENT_BATCH_SIZE = 5

_CONTEXT_PROMPT_TEMPLATE = (
    "You are a document analysis assistant. Given a document titled '{title}', "
    "generate a single concise sentence that explains the context of the "
    "following chunk — specifically, where it fits in the overall document and "
    "what topic it covers. Respond with ONLY the context sentence, nothing else.\n\n"
    "Chunk:\n{chunk_text}"
)


async def enrich_chunk(
    chunk_text: str,
    document_title: str,
    full_content: str,
    http_client: httpx.AsyncClient,
) -> str:
    """Generate a contextual prefix for a chunk using Ollama.

    Calls the configured CHAT_MODEL to produce a one-sentence summary of
    where ``chunk_text`` fits within the document. The context sentence is
    prepended to the chunk text so that embeddings capture richer meaning.

    If enrichment fails for any reason, the original chunk text is returned
    unchanged — enrichment is best-effort and must never block ingestion.

    Parameters
    ----------
    chunk_text : str
        The raw chunk content to enrich.
    document_title : str
        Title or filename of the source document (used in the prompt).
    full_content : str
        The full document text (reserved for future multi-shot context;
        currently unused to keep prompts small and fast).
    http_client : httpx.AsyncClient
        Shared HTTP client for Ollama requests.

    Returns
    -------
    str
        The enriched chunk text with context prepended, or the original
        chunk text if enrichment fails.
    """
    prompt = _CONTEXT_PROMPT_TEMPLATE.format(
        title=document_title,
        chunk_text=chunk_text[:2000],  # limit to avoid huge prompts
    )

    try:
        response = await http_client.post(
            f"{settings.OLLAMA_URL}/api/chat",
            json={
                "model": settings.CHAT_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 100},
            },
            timeout=30.0,
        )
        response.raise_for_status()
        context_sentence = (
            response.json()
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if context_sentence:
            return f"[Context: {context_sentence}] {chunk_text}"
        return chunk_text
    except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError) as exc:
        logger.warning(
            "Chunk enrichment failed (returning original): %s", exc
        )
        return chunk_text


async def enrich_chunks_batch(
    chunks: List[Dict],
    document_title: str,
    full_content: str,
    http_client: httpx.AsyncClient,
    batch_size: int = _ENRICHMENT_BATCH_SIZE,
) -> List[Dict]:
    """Enrich a list of chunk dicts, processing in batches to limit concurrency.

    Each chunk dict must have a ``content`` key. The enriched text replaces
    the ``content`` value in-place (a new dict is returned per chunk to
    preserve immutability of the originals).

    Parameters
    ----------
    chunks : list of dict
        Chunk dicts as produced by the chunking module.
    document_title : str
        Document title passed to enrichment prompt.
    full_content : str
        Full document text (reserved for future use).
    http_client : httpx.AsyncClient
        Shared HTTP client.
    batch_size : int
        Max concurrent enrichment calls per batch.

    Returns
    -------
    list of dict
        New chunk dicts with enriched ``content`` values.
    """
    enriched_chunks: List[Dict] = []

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        enriched_texts = await asyncio.gather(
            *[
                enrich_chunk(
                    chunk["content"],
                    document_title,
                    full_content,
                    http_client,
                )
                for chunk in batch
            ],
            return_exceptions=True,
        )
        for chunk, enriched in zip(batch, enriched_texts):
            if isinstance(enriched, BaseException):
                logger.warning("Enrichment exception for chunk %s: %s", chunk.get("index"), enriched)
                enriched_chunks.append({**chunk})
            else:
                enriched_chunks.append({**chunk, "content": enriched})

    return enriched_chunks
