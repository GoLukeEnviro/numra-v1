from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        correlation_id = request.headers.get("x-correlation-id", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-Id"] = correlation_id
        return response


class RequestBodyLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_bytes: int) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > self.max_bytes:
            from starlette.responses import JSONResponse

            return JSONResponse(
                status_code=413,
                content={"code": "REQUEST_BODY_TOO_LARGE", "message": "request body exceeds limit"},
            )
        return await call_next(request)


class OriginValidationMiddleware(BaseHTTPMiddleware):
    """Rejects state-changing requests whose Origin header is not in the allowlist. Runs
    before CORSMiddleware so a forged Origin never reaches application routes."""

    def __init__(self, app, allowed_origins: list[str]) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.allowed_origins = set(allowed_origins)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            origin = request.headers.get("origin")
            if origin is not None and origin not in self.allowed_origins:
                from starlette.responses import JSONResponse

                return JSONResponse(
                    status_code=403,
                    content={"code": "ORIGIN_NOT_ALLOWED", "message": "origin not allowed"},
                )
        return await call_next(request)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """PII-safe structured access log: never logs names, birth data, or bodies — only
    method, path, status, latency, and correlation id."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        import logging

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logging.getLogger("numra_api.access").info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "correlation_id": getattr(request.state, "correlation_id", None),
            },
        )
        return response
