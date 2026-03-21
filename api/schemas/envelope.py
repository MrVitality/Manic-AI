"""Standardized API response envelope."""

from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Field-level validation error detail."""

    field: str
    message: str
    code: str


class ApiError(BaseModel):
    """Structured error object with machine-readable code."""

    code: str
    message: str
    details: Optional[List[ErrorDetail]] = None


class ApiResponse(BaseModel, Generic[T]):
    """Uniform envelope for all API responses.

    - ``success``: True when the request completed without errors.
    - ``data``: The payload (None on error).
    - ``error``: Structured error object (None on success).
    - ``meta``: Optional metadata (pagination, timing, etc.).
    """

    success: bool
    data: Optional[T] = None
    error: Optional[ApiError] = None
    meta: Optional[Dict[str, Any]] = None


def ok(data: Any = None, *, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Shorthand for a successful envelope dict (FastAPI serialises dicts)."""
    return {"success": True, "data": data, "error": None, "meta": meta}


def fail(
    code: str,
    message: str,
    *,
    details: Optional[List[Dict[str, str]]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Shorthand for an error envelope dict with structured error."""
    error = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {"success": False, "data": None, "error": error, "meta": meta}
