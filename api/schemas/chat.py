"""Chat request / response schemas."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(system|user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 2048
    stream: Optional[bool] = False
    use_rag: Optional[bool] = False
    collection_id: Optional[str] = None
    user_id: Optional[str] = None


class ChatResponse(BaseModel):
    id: str
    model: str
    message: ChatMessage
    sources: List[Dict] = []
    usage: Dict = {}
