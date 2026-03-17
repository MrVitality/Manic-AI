"""Standardized API response envelope."""

from typing import Any, Dict, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Uniform envelope for all API responses.

    - ``success``: True when the request completed without errors.
    - ``data``: The payload (None on error).
    - ``error``: Human-readable error string (None on success).
    - ``meta``: Optional metadata (pagination, timing, etc.).
    """

    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


def ok(data: Any = None, *, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Shorthand for a successful envelope dict (FastAPI serialises dicts)."""
    return {"success": True, "data": data, "error": None, "meta": meta}


def fail(error: str, *, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Shorthand for an error envelope dict."""
    return {"success": False, "data": None, "error": error, "meta": meta}
