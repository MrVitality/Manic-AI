"""Model management schemas."""

from pydantic import BaseModel, Field


class PullModelRequest(BaseModel):
    name: str = Field(..., max_length=200)
