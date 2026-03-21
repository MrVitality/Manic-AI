"""Prometheus metrics middleware for request instrumentation."""

import time

from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# Request counter by method, path, and status code
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

# Request latency histogram
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Active requests gauge (optional, useful for monitoring concurrency)
REQUESTS_IN_PROGRESS = Counter(
    "http_requests_in_progress_total",
    "HTTP requests currently being processed",
    ["method"],
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Instrument all HTTP requests with Prometheus metrics."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Normalize path to avoid high-cardinality labels
        path = request.url.path
        # Collapse UUID-like segments to reduce label cardinality
        parts = path.split("/")
        normalized = "/".join(
            ":id" if len(p) > 20 and not p.startswith("v") else p
            for p in parts
        )

        method = request.method
        start = time.perf_counter()

        response = await call_next(request)

        duration = time.perf_counter() - start
        status = str(response.status_code)

        REQUEST_COUNT.labels(method=method, path=normalized, status=status).inc()
        REQUEST_LATENCY.labels(method=method, path=normalized).observe(duration)

        return response
