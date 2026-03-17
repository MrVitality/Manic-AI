"""Repository protocol definitions.

These protocols define the contracts that concrete repository implementations
must satisfy. Business logic depends on these abstractions, not on concrete
storage backends.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class VectorStore(Protocol):
    """Protocol for vector similarity search backends (pgvector, Qdrant)."""

    async def vector_search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        threshold: float = 0.7,
        collection_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        ...

    async def hybrid_search(
        self,
        query_text: str,
        query_embedding: List[float],
        top_k: int = 5,
        keyword_weight: float = 0.3,
        collection_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        ...

    async def upsert(
        self,
        collection_name: str,
        points: List[Dict[str, Any]],
    ) -> bool:
        ...

    async def delete_by_document(
        self,
        collection_name: str,
        document_id: str,
    ) -> bool:
        ...


@runtime_checkable
class DocumentStore(Protocol):
    """Protocol for document and collection CRUD operations."""

    async def list_documents(
        self,
        user_id: Optional[str] = None,
        collection_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        ...

    async def delete_document(self, document_id: str) -> bool:
        ...

    async def insert_document(
        self,
        document_id: str,
        user_id: Optional[str],
        filename: str,
        content_type: str,
        file_size: int,
        chunk_count: int,
        metadata: str,
    ) -> None:
        ...

    async def link_document_collection(
        self,
        document_id: str,
        collection_id: str,
    ) -> None:
        ...

    async def insert_chunk(
        self,
        document_id: str,
        chunk_index: int,
        content: str,
        content_tokens: int,
        embedding_str: str,
        metadata: str,
    ) -> None:
        ...

    async def mark_document_completed(self, document_id: str) -> None:
        ...

    async def mark_document_failed(self, document_id: str, error: str) -> None:
        ...

    async def list_collections(
        self,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        ...

    async def create_collection(
        self,
        collection_id: str,
        user_id: Optional[str],
        name: str,
        description: Optional[str],
        is_public: bool,
    ) -> None:
        ...

    async def delete_collection(self, collection_id: str) -> bool:
        ...

    async def get_document_chunks(
        self,
        document_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        ...

    async def get_document_filenames(
        self,
        document_ids: List[str],
    ) -> Dict[str, str]:
        ...


@runtime_checkable
class CacheStore(Protocol):
    """Protocol for caching (Redis or other KV stores)."""

    async def get(self, key: str) -> Optional[str]:
        ...

    async def setex(self, key: str, ttl: int, value: str) -> None:
        ...

    async def delete_pattern(self, pattern: str) -> int:
        ...
