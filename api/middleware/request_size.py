"""Reject requests whose Content-Length exceeds a configured maximum.

This middleware guards against abusive payloads before any route handler
or body parser runs.  It relies solely on the ``Content-Length`` header;
chunked-encoded requests without a declared length are passed through
unchanged (the application layer is responsible for bounded streaming reads).
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# 50 MB — generous enough for document ingest, tight enough to prevent abuse.
MAX_BODY_SIZE: int = 50 * 1024 * 1024
_MAX_MB: int = MAX_BODY_SIZE // (1024 * 1024)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "bad_request",
                            "message": "Invalid Content-Length header",
                        },
                        "meta": None,
                    },
                )
            if declared > MAX_BODY_SIZE:
                return JSONResponse(
                    status_code=413,
                    content={
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "payload_too_large",
                            "message": f"Request body exceeds {_MAX_MB}MB limit",
                        },
                        "meta": None,
                    },
                )
        elif request.method in ("POST", "PUT", "PATCH"):
            # No Content-Length on a body-bearing method — reject to prevent
            # unbounded memory buffering from chunked uploads.
            return JSONResponse(
                status_code=411,
                content={
                    "success": False,
                    "data": None,
                    "error": {
                        "code": "length_required",
                        "message": "Content-Length header is required",
                    },
                    "meta": None,
                },
            )
        return await call_next(request)
