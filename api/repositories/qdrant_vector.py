"""Qdrant vector store repository."""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class QdrantVectorRepository:
    """Wraps all HTTP calls to the Qdrant REST API."""

    def __init__(self, base_url: str, client: httpx.AsyncClient) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client

    async def search(
        self,
        query_embedding: List[float],
        collection_name: str = "documents",
        top_k: int = 5,
        threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "vector": query_embedding,
            "limit": top_k,
            "score_threshold": threshold,
            "with_payload": True,
            "with_vectors": False,
        }
        if filters:
            payload["filter"] = {
                "must": [{"key": k, "match": {"value": v}} for k, v in filters.items() if v]
            }
        try:
            response = await self._client.post(
                f"{self._base_url}/collections/{collection_name}/points/search",
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            return [
                {
                    "id": str(r["id"]),
                    "document_id": r.get("payload", {}).get("document_id", ""),
                    "content": r.get("payload", {}).get("content", ""),
                    "metadata": r.get("payload", {}).get("metadata", {}),
                    "score": float(r["score"]),
                    "backend": "qdrant",
                }
                for r in response.json().get("result", [])
            ]
        except Exception as e:
            logger.error("Qdrant search: %s", e)
            return []

    async def upsert(
        self,
        collection_name: str,
        points: List[Dict[str, Any]],
    ) -> bool:
        try:
            response = await self._client.put(
                f"{self._base_url}/collections/{collection_name}/points",
                json={"points": points},
                timeout=60.0,
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error("Qdrant upsert: %s", e)
            return False

    async def delete_by_document(
        self,
        collection_name: str,
        document_id: str,
    ) -> bool:
        try:
            response = await self._client.post(
                f"{self._base_url}/collections/{collection_name}/points/delete",
                json={
                    "filter": {
                        "must": [{"key": "document_id", "match": {"value": document_id}}]
                    }
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error("Qdrant delete: %s", e)
            return False

    async def ensure_collection(
        self,
        collection_name: str,
        vector_size: int,
    ) -> bool:
        try:
            r = await self._client.get(
                f"{self._base_url}/collections/{collection_name}", timeout=10.0,
            )
            if r.status_code == 200:
                return True
            r = await self._client.put(
                f"{self._base_url}/collections/{collection_name}",
                json={"vectors": {"size": vector_size, "distance": "Cosine"}},
                timeout=10.0,
            )
            return r.status_code in [200, 201]
        except Exception as e:
            logger.error("Qdrant ensure collection: %s", e)
            return False

    async def list_collections(self) -> Any:
        response = await self._client.get(f"{self._base_url}/collections")
        response.raise_for_status()
        return response.json()

    async def get_collection(self, collection_name: str) -> Any:
        response = await self._client.get(
            f"{self._base_url}/collections/{collection_name}",
        )
        response.raise_for_status()
        return response.json()

    async def create_collection(
        self, collection_name: str, vector_size: int = 768,
    ) -> Dict[str, str]:
        response = await self._client.put(
            f"{self._base_url}/collections/{collection_name}",
            json={"vectors": {"size": vector_size, "distance": "Cosine"}},
        )
        if response.status_code in [200, 201]:
            return {"status": "created", "collection": collection_name}
        if response.status_code == 409:
            return {"status": "exists", "collection": collection_name}
        raise httpx.HTTPStatusError(
            f"Unexpected status {response.status_code}",
            request=response.request,
            response=response,
        )

    async def delete_collection(self, collection_name: str) -> Dict[str, str]:
        response = await self._client.delete(
            f"{self._base_url}/collections/{collection_name}",
        )
        if response.status_code in [200, 204]:
            return {"status": "deleted", "collection": collection_name}
        raise httpx.HTTPStatusError(
            f"Unexpected status {response.status_code}",
            request=response.request,
            response=response,
        )
