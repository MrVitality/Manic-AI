from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import json
import httpx

from api.database import get_db
from api.http_client import get_client
from api.services.rag import qdrant_delete_by_document

router = APIRouter()


@router.get("/documents")
async def list_documents(
    user_id: Optional[str] = None,
    collection_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500),
    db=Depends(get_db),
):
    async with db.acquire() as conn:
        results = await conn.fetch(
            """
            SELECT
                d.id::text,
                d.filename,
                d.content_type,
                d.file_size,
                d.status,
                d.chunk_count,
                d.metadata,
                d.created_at,
                d.updated_at
            FROM rag.documents d
            LEFT JOIN rag.document_collections dc ON d.id = dc.document_id
            WHERE
                ($1::uuid IS NULL OR d.user_id = $1::uuid)
                AND ($2::uuid IS NULL OR dc.collection_id = $2::uuid)
                AND ($3::text IS NULL OR d.status = $3)
            ORDER BY d.created_at DESC
            LIMIT $4
            """,
            user_id,
            collection_id,
            status,
            limit,
        )
        return [
            {
                "id": r["id"],
                "filename": r["filename"],
                "content_type": r["content_type"],
                "file_size": r["file_size"],
                "status": r["status"],
                "chunk_count": r["chunk_count"],
                "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
            for r in results
        ]


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    db=Depends(get_db),
    client: httpx.AsyncClient = Depends(get_client),
):
    async with db.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM rag.documents WHERE id = $1", document_id
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Document not found")

    # Clean up orphaned Qdrant vectors for this document.
    # qdrant_delete_by_document returns bool; failure is non-fatal so the
    # return value is intentionally discarded.
    await qdrant_delete_by_document("documents", document_id, client)

    return {"status": "deleted", "document_id": document_id}
