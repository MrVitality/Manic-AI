"""Chat request / response schemas."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(system|user|assistant)$")
    content: str = Field(..., max_length=100_000)


class Citation(BaseModel):
    """Structured citation pointing back to a RAG source chunk."""

    source_id: str = Field(..., description="Chunk UUID from the vector store")
    document_id: str = Field(..., description="Parent document UUID")
    chunk_index: int = Field(0, description="Chunk index within the document")
    content_preview: str = Field("", description="First ~200 chars of the chunk")
    score: float = Field(0.0, description="Retrieval similarity score")


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 2048
    stream: Optional[bool] = False
    use_rag: Optional[bool] = False
    collection_id: Optional[str] = None
    user_id: Optional[str] = None
    rerank: Optional[bool] = False
    context_window: Optional[int] = None


class ChatResponse(BaseModel):
    id: str
    model: str
    message: ChatMessage
    sources: List[Dict] = []
    citations: List[Citation] = []
    usage: Dict = {}
