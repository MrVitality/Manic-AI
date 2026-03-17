"""Search request / response schemas."""

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5
    threshold: Optional[float] = 0.7
    use_hybrid: Optional[bool] = True
    collection_id: Optional[str] = None
    user_id: Optional[str] = None
    backend: Literal["supabase", "qdrant", "both"] = "supabase"


class SearchResult(BaseModel):
    id: str
    document_id: str
    content: str
    metadata: Dict[str, Any]
    score: float


class SearchExplainRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5
    threshold: Optional[float] = 0.5
    use_hybrid: Optional[bool] = True
    collection_id: Optional[str] = None
    include_vectors: Optional[bool] = False
    backend: Literal["supabase", "qdrant", "both"] = "supabase"
