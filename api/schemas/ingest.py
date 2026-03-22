"""Ingest / embed request and response schemas."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class EmbedRequest(BaseModel):
    text: str = Field(..., max_length=50_000)
    model: Optional[str] = None


class EmbedResponse(BaseModel):
    embedding: List[float]
    model: str
    dimensions: int


class IngestRequest(BaseModel):
    content: str = Field(..., max_length=10_000_000)
    filename: str = Field(..., max_length=255, pattern=r"^[^\x00/\\]+$")
    content_type: Optional[str] = Field(
        default="text/plain",
        pattern=r"^[a-zA-Z0-9!#$&\-^_]+/[a-zA-Z0-9!#$&\-^_.+]+$",
    )
    user_id: Optional[str] = None
    collection_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    chunk_size: int = Field(default=500, ge=1, le=10000)
    chunk_overlap: int = Field(default=50, ge=0)
    backend: Literal["supabase", "qdrant", "both"] = "both"
    chunking_strategy: Literal["simple", "semantic"] = "simple"
    enrich_context: bool = Field(
        default=False,
        description="When True, each chunk is enriched with a contextual summary "
        "via LLM before embedding, improving retrieval quality.",
    )
    multimodal: bool = Field(
        default=False,
        description="When True and content_type is 'application/pdf', uses ColPali-style "
        "multimodal ingestion: converts pages to images, describes via vision LLM, "
        "then embeds the descriptions.",
    )

    @model_validator(mode="after")
    def validate_overlap_less_than_size(self):
        if self.chunking_strategy == "simple" and self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be less than chunk_size ({self.chunk_size})"
            )
        return self


class IngestResponse(BaseModel):
    document_id: str
    filename: str
    chunks_created: int
    status: str


class IngestAccepted(BaseModel):
    """Returned immediately when an async ingest job is accepted."""
    document_id: str
    status: Literal["pending", "processing"] = "processing"


class IngestStatusResponse(BaseModel):
    """Returned by the status-polling endpoint."""
    document_id: str
    status: Literal["pending", "processing", "completed", "failed"]
    filename: Optional[str] = None
    chunks_created: Optional[int] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
