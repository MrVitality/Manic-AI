"""Global exception handlers for consistent envelope-format error responses.

Register all handlers by calling ``register_exception_handlers(app)`` after
the FastAPI application is created.  This module supersedes the default
slowapi ``_rate_limit_exceeded_handler`` — do NOT register that handler
alongside these.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from api.schemas.envelope import fail

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status-code → machine-readable error-code mapping
# ---------------------------------------------------------------------------

_HTTP_STATUS_TO_CODE: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    429: "rate_limit_exceeded",
    500: "internal_error",
    502: "bad_gateway",
    503: "service_unavailable",
}

_DEFAULT_ERROR_CODE = "internal_error"


def _code_for_status(status: int) -> str:
    return _HTTP_STATUS_TO_CODE.get(status, _DEFAULT_ERROR_CODE)


# ---------------------------------------------------------------------------
# Individual handlers
# ---------------------------------------------------------------------------


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Wrap FastAPI/Starlette HTTPException in the standard envelope."""
    error_code = _code_for_status(exc.status_code)

    # exc.detail can be a str or an arbitrary dict; coerce to str for the
    # envelope message field so clients always get a plain string.
    message: str
    if isinstance(exc.detail, str):
        message = exc.detail
    else:
        message = str(exc.detail)

    body = fail(error_code, message)

    headers: dict[str, Any] = {}
    if exc.headers:
        headers.update(exc.headers)

    return JSONResponse(status_code=exc.status_code, content=body, headers=headers or None)


async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Wrap Pydantic RequestValidationError in the standard envelope.

    Each Pydantic error is normalised to ``{field, message, code}`` so the
    client can map errors back to individual form fields.
    """
    details: list[dict[str, str]] = []
    for error in exc.errors():
        # ``loc`` is a tuple like ("body", "field_name") or ("query", "param").
        # Drop the first segment ("body"/"query"/…) and join the rest.
        loc_parts = error.get("loc", ())
        field = ".".join(str(p) for p in loc_parts[1:]) if len(loc_parts) > 1 else str(loc_parts[0]) if loc_parts else "unknown"

        details.append(
            {
                "field": field,
                "message": error.get("msg", "Invalid value"),
                "code": error.get("type", "value_error"),
            }
        )

    body = fail(
        "validation_error",
        "Request validation failed",
        details=details,
    )
    return JSONResponse(status_code=422, content=body)


async def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Wrap slowapi RateLimitExceeded in the standard envelope.

    Preserves the ``Retry-After`` header when slowapi provides one so clients
    can implement back-off correctly.
    """
    body = fail("rate_limit_exceeded", "Rate limit exceeded. Try again later.")

    headers: dict[str, str] = {}
    # slowapi stores the retry-after value on the exception as a string.
    retry_after: str | None = getattr(exc, "retry_after", None)
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)

    return JSONResponse(status_code=429, content=body, headers=headers or None)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for any exception not handled by a more specific handler.

    Logs the full traceback server-side but returns only a generic message to
    the client so internal implementation details are never leaked.
    """
    logger.exception(
        "Unhandled exception for %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )

    body = fail("internal_error", "An unexpected error occurred")
    return JSONResponse(status_code=500, content=body)


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


def register_exception_handlers(app: FastAPI) -> None:
    """Register all global exception handlers on *app*.

    Call this inside ``create_app()`` **instead of** registering slowapi's
    default ``_rate_limit_exceeded_handler``.  The order of registration does
    not affect dispatch priority — FastAPI/Starlette resolves handlers by
    exception type specificity (most-derived class wins).
    """
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)  # type: ignore[arg-type]
