"""Request timing middleware — logs method, path, status code, and duration."""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("api.metrics")


class MetricsMiddleware(BaseHTTPMiddleware):
    """Measure and log the wall-clock duration of every HTTP request."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000.0

        logger.info(
            "method=%s path=%s status=%d duration_ms=%.2f",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

        # Expose timing as a response header for client-side observability
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"
        return response
