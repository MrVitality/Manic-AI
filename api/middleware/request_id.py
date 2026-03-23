"""Request ID middleware — attaches a unique X-Request-ID to every request/response."""

from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from api.logging_config import request_id_var

HEADER = "X-Request-ID"


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Ensure every request carries a unique request ID.

    If the caller already supplies an ``X-Request-ID`` header it is preserved;
    otherwise a new UUID4 is generated.  The ID is always returned in the
    response headers so callers can correlate logs.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get(HEADER) or str(uuid4())

        # Store on request state so downstream handlers can access it
        request.state.request_id = request_id

        # Propagate into contextvars so all log records carry the request ID
        token = request_id_var.set(request_id)
        try:
            response: Response = await call_next(request)
            response.headers[HEADER] = request_id
        finally:
            request_id_var.reset(token)
        return response
