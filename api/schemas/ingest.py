"""Ingest / embed request and response schemas."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class EmbedRequest(BaseModel):
    text: str
    model: Optional[str] = None


class EmbedResponse(BaseModel):
    embedding: List[float]
    model: str
    dimensions: int


class IngestRequest(BaseModel):
    content: str
    filename: str
    content_type: Optional[str] = "text/plain"
    user_id: Optional[str] = None
    collection_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    chunk_size: int = Field(default=500, ge=1, le=10000)
    chunk_overlap: int = Field(default=50, ge=0)
    backend: Literal["supabase", "qdrant", "both"] = "both"

    @model_validator(mode="after")
    def validate_overlap_less_than_size(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be less than chunk_size ({self.chunk_size})"
            )
        return self


class IngestResponse(BaseModel):
    document_id: str
    filename: str
    chunks_created: int
    status: str
