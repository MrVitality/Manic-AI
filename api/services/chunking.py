"""Text chunking strategies for RAG document ingestion.

Supports two strategies:
- "simple": Original character-based splitter with sentence-boundary awareness.
- "semantic": Recursive splitter (markdown headers -> paragraphs -> sentences)
  with parent-child chunk support for better retrieval context.
"""

import re
from typing import Dict, List, Literal

# ---------------------------------------------------------------------------
# Simple chunking (original implementation, kept as fallback)
# ---------------------------------------------------------------------------


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[Dict]:
    """Original simple chunker -- character-based with sentence-boundary snapping."""
    # Guard against infinite loop: overlap must be less than half of chunk_size
    # to ensure forward progress on every iteration.
    if overlap >= chunk_size // 2:
        overlap = max(0, chunk_size // 2 - 1)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = " ".join(text.split())
    if len(text) <= chunk_size:
        return [{"content": text, "index": 0, "start": 0, "end": len(text)}]
    chunks = []
    start = 0
    index = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            last_period = text.rfind(".", start, end)
            last_newline = text.rfind("\n", start, end)
            break_point = max(last_period, last_newline)
            if break_point > start + chunk_size * 0.5:
                end = break_point + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append({"content": chunk, "index": index, "start": start, "end": end})
            index += 1
        start = end - overlap
        if start >= len(text) - overlap:
            break
    return chunks


# ---------------------------------------------------------------------------
# Semantic chunking (recursive: headers -> paragraphs -> sentences)
# ---------------------------------------------------------------------------

# Markdown header pattern (ATX-style: # through ######)
_MD_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# Sentence boundary: period/question/exclamation followed by space or end
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _split_by_markdown_headers(text: str) -> List[Dict[str, str]]:
    """Split text into sections delimited by markdown headers.

    Returns a list of dicts with 'header' (may be empty) and 'body'.
    """
    sections: List[Dict[str, str]] = []
    matches = list(_MD_HEADER_RE.finditer(text))

    if not matches:
        return [{"header": "", "body": text.strip()}]

    # Text before the first header
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append({"header": "", "body": preamble})

    for i, match in enumerate(matches):
        header = match.group(0).strip()
        body_start = match.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        sections.append({"header": header, "body": body})

    return sections


def _split_into_paragraphs(text: str) -> List[str]:
    """Split text into paragraphs (double-newline separated blocks)."""
    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if p.strip()]


def _split_into_sentences(text: str) -> List[str]:
    """Split text into sentences."""
    sentences = _SENTENCE_RE.split(text)
    return [s.strip() for s in sentences if s.strip()]


def _estimate_tokens(text: str) -> int:
    """Quick token estimate (chars / 4)."""
    return max(1, len(text) // 4)


def _build_chunks_from_segments(
    segments: List[str],
    target_tokens: int,
    overlap_tokens: int = 0,
) -> List[str]:
    """Greedily combine text segments into chunks up to target_tokens."""
    chunks: List[str] = []
    current_parts: List[str] = []
    current_tokens = 0

    for segment in segments:
        seg_tokens = _estimate_tokens(segment)
        if current_tokens + seg_tokens > target_tokens and current_parts:
            chunks.append(" ".join(current_parts))
            # overlap: keep last few parts
            if overlap_tokens > 0:
                overlap_parts: List[str] = []
                overlap_count = 0
                for part in reversed(current_parts):
                    part_tokens = _estimate_tokens(part)
                    if overlap_count + part_tokens > overlap_tokens:
                        break
                    overlap_parts.insert(0, part)
                    overlap_count += part_tokens
                current_parts = overlap_parts
                current_tokens = overlap_count
            else:
                current_parts = []
                current_tokens = 0
        current_parts.append(segment)
        current_tokens += seg_tokens

    if current_parts:
        chunks.append(" ".join(current_parts))

    return chunks


def semantic_chunk_text(
    text: str,
    retrieval_token_size: int = 200,
    context_token_size: int = 1000,
    overlap_tokens: int = 20,
) -> List[Dict]:
    """Recursively chunk text using markdown structure.

    Produces retrieval-sized chunks (~200 tokens) with parent context chunks
    (~1000 tokens). Each chunk dict contains:
    - content: the retrieval chunk text
    - parent_content: the larger context chunk this belongs to
    - index: sequential chunk index
    - start / end: character offsets in original text
    - header: the markdown section header (if any)

    The recursive splitting order is:
    1. Markdown headers (sections)
    2. Paragraphs (double newlines)
    3. Sentences (period/question/exclamation boundaries)
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    original_text = text

    sections = _split_by_markdown_headers(text)

    # First pass: build context-sized parent chunks per section
    parent_chunks: List[Dict] = []
    for section in sections:
        header = section["header"]
        body = section["body"]
        if not body:
            continue

        paragraphs = _split_into_paragraphs(body)
        if not paragraphs:
            continue

        # Build parent (context) chunks from paragraphs
        parent_texts = _build_chunks_from_segments(paragraphs, context_token_size)
        for ptext in parent_texts:
            parent_content = f"{header}\n\n{ptext}".strip() if header else ptext
            parent_chunks.append({
                "header": header,
                "parent_content": parent_content,
                "body": ptext,
            })

    # Second pass: split each parent chunk into retrieval-sized child chunks
    all_chunks: List[Dict] = []
    chunk_index = 0

    for parent in parent_chunks:
        body = parent["body"]
        header = parent["header"]
        parent_content = parent["parent_content"]

        # Split body into sentences, then build retrieval chunks
        sentences = _split_into_sentences(body)
        if not sentences:
            sentences = [body]

        retrieval_texts = _build_chunks_from_segments(
            sentences, retrieval_token_size, overlap_tokens
        )

        for rtext in retrieval_texts:
            rtext = rtext.strip()
            if not rtext:
                continue

            # Find character offsets in original text
            start_pos = original_text.find(rtext[:50])
            start = max(0, start_pos) if start_pos >= 0 else 0
            end = start + len(rtext)

            all_chunks.append({
                "content": rtext,
                "parent_content": parent_content,
                "index": chunk_index,
                "start": start,
                "end": end,
                "header": header,
            })
            chunk_index += 1

    # Fallback: if semantic splitting produced nothing, use simple chunking
    if not all_chunks:
        return chunk_text(text, chunk_size=retrieval_token_size * 4, overlap=overlap_tokens * 4)

    return all_chunks


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------


def chunk_document(
    text: str,
    strategy: Literal["simple", "semantic"] = "simple",
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    retrieval_token_size: int = 200,
    context_token_size: int = 1000,
) -> List[Dict]:
    """Chunk a document using the specified strategy.

    Parameters
    ----------
    text : str
        The full document text to chunk.
    strategy : "simple" | "semantic"
        Which chunking algorithm to use.
    chunk_size : int
        Character-based chunk size for simple strategy.
    chunk_overlap : int
        Character overlap for simple strategy.
    retrieval_token_size : int
        Target token size for retrieval chunks (semantic strategy).
    context_token_size : int
        Target token size for parent context chunks (semantic strategy).

    Returns
    -------
    List of chunk dicts. All chunks have at minimum:
        content, index, start, end.
    Semantic chunks additionally have: parent_content, header.
    """
    if strategy == "semantic":
        return semantic_chunk_text(
            text,
            retrieval_token_size=retrieval_token_size,
            context_token_size=context_token_size,
        )
    return chunk_text(text, chunk_size=chunk_size, overlap=chunk_overlap)
