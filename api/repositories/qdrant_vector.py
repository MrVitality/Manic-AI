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
            "params": {"hnsw_ef": 128},
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

    async def search_with_vectors(
        self,
        query_embedding: List[float],
        collection_name: str = "documents",
        top_k: int = 5,
        threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Same as :meth:`search` but also returns the stored vector for each hit.

        The returned dicts include an ``"embedding"`` key containing the point's
        vector as a plain ``list[float]``, which callers can pass directly to
        :func:`~api.services.mmr.mmr_rerank`.
        """
        payload: Dict[str, Any] = {
            "vector": query_embedding,
            "limit": top_k,
            "score_threshold": threshold,
            "with_payload": True,
            "with_vectors": True,
            "params": {"hnsw_ef": 128},
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
            results = []
            for r in response.json().get("result", []):
                # Qdrant may return a list (unnamed vectors) or a dict (named).
                raw_vec = r.get("vector")
                embedding: List[float] = raw_vec if isinstance(raw_vec, list) else []
                results.append({
                    "id": str(r["id"]),
                    "document_id": r.get("payload", {}).get("document_id", ""),
                    "content": r.get("payload", {}).get("content", ""),
                    "metadata": r.get("payload", {}).get("metadata", {}),
                    "score": float(r["score"]),
                    "backend": "qdrant",
                    "embedding": embedding,
                })
            return results
        except Exception as e:
            logger.error("Qdrant search_with_vectors: %s", e)
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

    async def _create_payload_index(
        self,
        collection_name: str,
        field_name: str,
        field_schema: str,
    ) -> None:
        """Create a payload index on *field_name* for faster filtered searches."""
        try:
            r = await self._client.put(
                f"{self._base_url}/collections/{collection_name}/index",
                json={"field_name": field_name, "field_schema": field_schema},
                timeout=10.0,
            )
            if r.status_code not in [200, 201]:
                logger.warning(
                    "Qdrant payload index (%s.%s): unexpected status %s",
                    collection_name, field_name, r.status_code,
                )
        except Exception as e:
            logger.warning("Qdrant payload index (%s.%s): %s", collection_name, field_name, e)

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
                json={
                    "vectors": {"size": vector_size, "distance": "Cosine"},
                    "hnsw_config": {
                        "m": 16,
                        "ef_construct": 200,
                    },
                    "quantization_config": {
                        "scalar": {
                            "type": "int8",
                            "quantile": 0.99,
                            "always_ram": True,
                        }
                    },
                },
                timeout=10.0,
            )
            if r.status_code not in [200, 201]:
                return False
            await self._create_payload_index(collection_name, "collection_id", "keyword")
            await self._create_payload_index(collection_name, "user_id", "keyword")
            return True
        except Exception as e:
            logger.error("Qdrant ensure collection: %s", e)
            return False

    async def list_collections(self) -> Any:
        response = await self._client.get(
            f"{self._base_url}/collections", timeout=10.0,
        )
        response.raise_for_status()
        return response.json()

    async def get_collection(self, collection_name: str) -> Any:
        response = await self._client.get(
            f"{self._base_url}/collections/{collection_name}",
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()

    async def create_collection(
        self, collection_name: str, vector_size: int = 1024,
    ) -> Dict[str, str]:
        response = await self._client.put(
            f"{self._base_url}/collections/{collection_name}",
            json={
                "vectors": {"size": vector_size, "distance": "Cosine"},
                "hnsw_config": {
                    "m": 16,
                    "ef_construct": 200,
                },
                "quantization_config": {
                    "scalar": {
                        "type": "int8",
                        "quantile": 0.99,
                        "always_ram": True,
                    }
                },
            },
            timeout=30.0,
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
            timeout=30.0,
        )
        if response.status_code in [200, 204]:
            return {"status": "deleted", "collection": collection_name}
        raise httpx.HTTPStatusError(
            f"Unexpected status {response.status_code}",
            request=response.request,
            response=response,
        )
