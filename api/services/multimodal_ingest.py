"""ColPali-style multimodal PDF ingestion.

Converts PDF pages to images, generates text descriptions via an Ollama
vision model, then stores the descriptions (with page references) in Qdrant
and/or Supabase for retrieval.
"""

import asyncio
import base64
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx

from api.config import settings
from api.repositories.qdrant_vector import QdrantVectorRepository
from api.services.embedding import generate_embedding

logger = logging.getLogger(__name__)

# Vision model used for page description -- override via env if needed
VISION_MODEL = "llava"


async def _describe_page_image(
    image_bytes: bytes,
    page_number: int,
    document_title: str,
    http_client: httpx.AsyncClient,
) -> str:
    """Send a page image to Ollama vision model and get a text description."""
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    prompt = (
        f"You are analyzing page {page_number} of the document '{document_title}'. "
        "Describe the content of this page in detail, including any text, tables, "
        "figures, charts, or diagrams. Preserve the semantic meaning and structure."
    )

    response = await http_client.post(
        f"{settings.OLLAMA_URL}/api/generate",
        json={
            "model": VISION_MODEL,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "options": {"temperature": 0.1},
        },
        timeout=120.0,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("response", "").strip()


def _pdf_pages_to_images(pdf_content: bytes) -> List[bytes]:
    """Convert each PDF page to a JPEG image using PyMuPDF (fitz).

    Returns a list of JPEG byte buffers, one per page.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF is required for multimodal PDF ingestion. "
            "Install it with: pip install PyMuPDF"
        ) from exc

    doc = fitz.open(stream=pdf_content, filetype="pdf")
    images: List[bytes] = []
    try:
        for page in doc:
            # Render at 150 DPI for a good quality/size balance
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes(output="jpeg")
            images.append(img_bytes)
    finally:
        doc.close()
    return images


async def ingest_pdf_as_images(
    pdf_content: bytes,
    document_title: str,
    db_pool: Optional[Any],
    http_client: httpx.AsyncClient,
    *,
    collection_id: Optional[str] = None,
    user_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> dict:
    """Ingest a PDF by converting pages to images and describing them via vision LLM.

    Parameters
    ----------
    pdf_content : bytes
        Raw PDF file bytes.
    document_title : str
        Human-readable title / filename for the document.
    db_pool : asyncpg.Pool or None
        Database pool (used for Supabase storage if available).
    http_client : httpx.AsyncClient
        Shared HTTP client for Ollama / Qdrant calls.
    collection_id : str, optional
        Restrict to a specific collection.
    user_id : str, optional
        Owner user identifier.
    metadata : dict, optional
        Extra metadata to attach to each point.

    Returns
    -------
    dict
        ``{"document_id": ..., "pages_processed": ..., "status": ...}``
    """
    document_id = str(uuid4())
    page_images = _pdf_pages_to_images(pdf_content)

    if not page_images:
        return {
            "document_id": document_id,
            "pages_processed": 0,
            "status": "failed",
            "error": "PDF contains no pages",
        }

    logger.info(
        "Multimodal ingest: %d pages from '%s' (doc %s)",
        len(page_images),
        document_title,
        document_id,
    )

    # Describe each page via vision model (sequential to avoid overloading Ollama)
    descriptions: List[str] = []
    for idx, img_bytes in enumerate(page_images):
        try:
            desc = await _describe_page_image(
                img_bytes, idx + 1, document_title, http_client,
            )
            descriptions.append(desc)
        except Exception:
            logger.warning(
                "Vision description failed for page %d of %s", idx + 1, document_title,
            )
            descriptions.append(f"[Page {idx + 1}: description unavailable]")

    # Generate embeddings for each page description
    embeddings = await asyncio.gather(
        *[generate_embedding(desc, client=http_client) for desc in descriptions],
        return_exceptions=True,
    )

    # Store in Qdrant
    qdrant = QdrantVectorRepository(settings.QDRANT_URL, http_client)
    await qdrant.ensure_collection("documents", settings.VECTOR_DIMENSION)

    points: List[Dict[str, Any]] = []
    for idx, (desc, emb) in enumerate(zip(descriptions, embeddings)):
        if isinstance(emb, BaseException):
            logger.warning(
                "Embedding failed for page %d of %s: %s", idx + 1, document_title, emb,
            )
            continue
        point_id = str(uuid4())
        points.append({
            "id": point_id,
            "vector": emb,
            "payload": {
                "document_id": document_id,
                "chunk_index": idx,
                "page_number": idx + 1,
                "content": desc,
                "filename": document_title,
                "user_id": user_id,
                "collection_id": collection_id,
                "metadata": {
                    **(metadata or {}),
                    "ingestion_mode": "multimodal",
                    "source_type": "pdf_page_image",
                },
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        })

    qdrant_ok = False
    if points:
        qdrant_ok = await qdrant.upsert("documents", points)

    # Optionally store in Supabase as well
    supabase_ok = False
    if db_pool and points:
        try:
            from api.repositories.supabase_documents import SupabaseDocumentRepository
            import json

            doc_repo = SupabaseDocumentRepository(db_pool)
            chunks = [
                {"index": idx, "content": desc, "metadata": {"page_number": idx + 1, "ingestion_mode": "multimodal"}}
                for idx, desc in enumerate(descriptions)
            ]
            valid_embeddings = [
                emb for emb in embeddings if not isinstance(emb, BaseException)
            ]
            if len(valid_embeddings) == len(chunks):
                await doc_repo.insert_document_with_chunks(
                    document_id=document_id,
                    user_id=user_id,
                    filename=document_title,
                    content_type="application/pdf",
                    file_size=len(pdf_content),
                    chunk_count=len(chunks),
                    metadata_json=json.dumps({
                        **(metadata or {}),
                        "ingestion_mode": "multimodal",
                    }),
                    collection_id=collection_id,
                    chunks=chunks,
                    chunk_embeddings=valid_embeddings,
                    raw_content="\n\n".join(descriptions),
                )
                supabase_ok = True
        except Exception:
            logger.warning("Supabase storage failed for multimodal doc %s", document_id)

    if qdrant_ok or supabase_ok:
        status = "completed"
    else:
        status = "failed"

    return {
        "document_id": document_id,
        "pages_processed": len(points),
        "total_pages": len(page_images),
        "status": status,
    }
