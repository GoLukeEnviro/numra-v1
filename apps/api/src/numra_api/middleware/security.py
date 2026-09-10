from __future__ import annotations

import logging
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# These are pure ASGI middlewares on purpose -- NOT starlette.middleware.base
# BaseHTTPMiddleware. BaseHTTPMiddleware defers the exit half of FastAPI
# "dependencies with yield" until after the response has already been sent to the
# client (and, with several stacked, runs only the innermost one reliably --
# fastapi/fastapi#5597, #8407). numra_api.deps.get_db commits the request's DB
# transaction in exactly that exit half, so with BaseHTTPMiddleware in the stack a
# write endpoint returns 2xx before its own COMMIT lands; the immediately following
# request, on a fresh connection, then does not see the row it just created. Pure
# ASGI middleware keeps FastAPI's post-0.106 ordering intact: the yield-teardown
# commit runs before the response leaves the process.


class CorrelationIdMiddleware:
    """Assigns/propagates an X-Correlation-Id per request. Stored on scope["state"]
    so downstream (routes, AccessLogMiddleware) can read it without re-parsing."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        correlation_id = Headers(scope=scope).get("x-correlation-id", str(uuid.uuid4()))
        scope.setdefault("state", {})["correlation_id"] = correlation_id

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["X-Correlation-Id"] = correlation_id
            await send(message)

        await self.app(scope, receive, send_wrapper)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
                headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
            await send(message)

        await self.app(scope, receive, send_wrapper)


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            content_length = Headers(scope=scope).get("content-length")
            if content_length is not None and int(content_length) > self.max_bytes:
                response = JSONResponse(
                    status_code=413,
                    content={
                        "code": "REQUEST_BODY_TOO_LARGE",
                        "message": "request body exceeds limit",
                    },
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


class OriginValidationMiddleware:
    """Rejects state-changing requests whose Origin header is not in the allowlist. Runs
    before CORSMiddleware so a forged Origin never reaches application routes."""

    def __init__(self, app: ASGIApp, allowed_origins: list[str]) -> None:
        self.app = app
        self.allowed_origins = set(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in ("POST", "PUT", "PATCH", "DELETE"):
            origin = Headers(scope=scope).get("origin")
            if origin is not None and origin not in self.allowed_origins:
                response = JSONResponse(
                    status_code=403,
                    content={"code": "ORIGIN_NOT_ALLOWED", "message": "origin not allowed"},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


class AccessLogMiddleware:
    """PII-safe structured access log: never logs names, birth data, or bodies — only
    method, path, status, latency, and correlation id."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status_code = 0

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            logging.getLogger("numra_api.access").info(
                "request",
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "status_code": status_code,
                    "duration_ms": round(duration_ms, 2),
                    "correlation_id": scope.get("state", {}).get("correlation_id"),
                },
            )
