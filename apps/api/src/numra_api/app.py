from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from numra_api.config import Settings, get_settings
from numra_api.db import build_engine, build_sessionmaker
from numra_api.middleware.security import (
    AccessLogMiddleware,
    CorrelationIdMiddleware,
    OriginValidationMiddleware,
    RequestBodyLimitMiddleware,
    SecurityHeadersMiddleware,
)
from numra_api.rate_limit import InMemoryRateLimiter, RateLimiter, RedisRateLimiter
from numra_api.routes import (
    account,
    admin,
    auth,
    calculations,
    exports,
    health,
    people,
    public,
    relationships,
    reports,
    system_info,
)
from numra_api.services.errors import ApplicationError
from numra_api.services.pdf_client import PdfServiceClient
from numra_api.storage.exports import LocalExportStorage


def _build_rate_limiter(settings: Settings) -> RateLimiter:
    if settings.rate_limit_backend == "redis":
        from redis.asyncio import from_url

        return RedisRateLimiter(from_url(settings.redis_url))
    return InMemoryRateLimiter()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Factory — no global state except the module-level ``app`` below."""
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = build_engine(resolved_settings.database_url)
        app.state.engine = engine
        app.state.sessionmaker = build_sessionmaker(engine)
        app.state.settings = resolved_settings
        yield
        await engine.dispose()

    app = FastAPI(title="NUMRA API", version="1.0.0", lifespan=lifespan)
    app.state.settings = resolved_settings
    app.state.export_storage = LocalExportStorage(Path(resolved_settings.export_storage_dir))
    app.state.pdf_client = PdfServiceClient(
        base_url=resolved_settings.pdf_internal_url or "",
        internal_token=resolved_settings.pdf_internal_token,
        timeout_seconds=resolved_settings.pdf_render_timeout_seconds,
    )
    app.state.rate_limiter = _build_rate_limiter(resolved_settings)

    # Middleware chain — order matters (outermost first, applied last-in-first-out by
    # Starlette so the LAST .add_middleware call runs FIRST on the request path).
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["content-type", "x-csrf-token"],
    )
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(
        RequestBodyLimitMiddleware, max_bytes=resolved_settings.request_body_max_bytes
    )
    app.add_middleware(
        OriginValidationMiddleware, allowed_origins=resolved_settings.cors_allowed_origins
    )

    @app.exception_handler(ApplicationError)
    async def handle_application_error(request: Request, exc: ApplicationError) -> JSONResponse:
        headers = {}
        retry_after_seconds = getattr(exc, "retry_after_seconds", None)
        if retry_after_seconds is not None:
            headers["Retry-After"] = str(retry_after_seconds)
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": str(exc)},
            headers=headers,
        )

    app.include_router(health.router)
    app.include_router(public.router)
    app.include_router(auth.router)
    app.include_router(people.router)
    app.include_router(calculations.router)
    app.include_router(relationships.router)
    app.include_router(reports.router)
    app.include_router(exports.router)
    app.include_router(account.router)
    app.include_router(system_info.router)
    app.include_router(admin.router)

    return app


app = create_app()
