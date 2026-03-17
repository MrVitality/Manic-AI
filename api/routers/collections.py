from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Dict, List, Optional
import asyncpg
import json
from uuid import uuid4

from api.database import get_db

router = APIRouter()


@router.get("/collections")
async def list_collections(user_id: Optional[str] = None, db: asyncpg.Pool = Depends(get_db)) -> List[Dict[str, Any]]:
    async with db.acquire() as conn:
        results = await conn.fetch(
            """
            SELECT
                c.id::text,
                c.name,
                c.description,
                c.is_public,
                c.embedding_model,
                c.metadata,
                c.created_at,
                COUNT(dc.document_id) as document_count
            FROM rag.collections c
            LEFT JOIN rag.document_collections dc ON c.id = dc.collection_id
            WHERE ($1::uuid IS NULL OR c.user_id = $1::uuid OR c.is_public = TRUE)
            GROUP BY c.id
            ORDER BY c.created_at DESC
            """,
            user_id,
        )
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "description": r["description"],
                "is_public": r["is_public"],
                "embedding_model": r["embedding_model"],
                "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                "document_count": r["document_count"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in results
        ]


@router.post("/collections")
async def create_collection(
    name: str,
    description: Optional[str] = None,
    user_id: Optional[str] = None,
    is_public: bool = False,
    db: asyncpg.Pool = Depends(get_db),
) -> Dict[str, str]:
    collection_id = str(uuid4())
    async with db.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO rag.collections (id, user_id, name, description, is_public)
            VALUES ($1, $2, $3, $4, $5)
            """,
            collection_id,
            user_id,
            name,
            description,
            is_public,
        )
    return {"id": collection_id, "name": name, "status": "created"}


@router.delete("/collections/{collection_id}")
async def delete_collection(collection_id: str, db: asyncpg.Pool = Depends(get_db)) -> Dict[str, str]:
    async with db.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM rag.collections WHERE id = $1", collection_id
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Collection not found")
        return {"status": "deleted", "collection_id": collection_id}
