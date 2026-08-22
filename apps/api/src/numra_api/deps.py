from __future__ import annotations

import datetime as dt
from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import Cookie, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.auth.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, csrf_tokens_match
from numra_api.auth.sessions import hash_session_token
from numra_api.config import Settings
from numra_api.models import Session as SessionModel
from numra_api.models import User
from numra_api.rate_limit import RateLimiter, pseudonymous_key
from numra_api.repositories.sessions import get_active_session_by_token_hash
from numra_api.repositories.users import get_user_by_id
from numra_api.services.errors import CsrfValidationFailed, NotAuthenticated, RateLimitExceeded
from numra_api.services.pdf_client import PdfServiceClient
from numra_api.storage.exports import ExportStorage


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    sessionmaker = request.app.state.sessionmaker
    async with sessionmaker() as session:
        yield session
        await session.commit()


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_export_storage(request: Request) -> ExportStorage:
    storage: ExportStorage = request.app.state.export_storage
    return storage


def get_pdf_client(request: Request) -> PdfServiceClient:
    client: PdfServiceClient = request.app.state.pdf_client
    return client


def get_rate_limiter(request: Request) -> RateLimiter:
    limiter: RateLimiter = request.app.state.rate_limiter
    return limiter


async def _enforce_rate_limit(
    *,
    raw_identity: str,
    scope: str,
    limit: int,
    window_seconds: int,
    settings: Settings,
    limiter: RateLimiter,
) -> None:
    key = f"{scope}:{pseudonymous_key(raw_identity, secret=settings.session_secret)}"
    result = await limiter.check(key=key, limit=limit, window_seconds=window_seconds)
    if not result.allowed:
        raise RateLimitExceeded(retry_after_seconds=result.retry_after_seconds)


def rate_limit_by_ip(
    scope: str, *, limit: int, window_seconds: int
) -> Callable[..., Awaitable[None]]:
    """A FastAPI dependency limiting requests per client IP — for unauthenticated
    endpoints (login, register) where there is no user id yet to key on. The IP itself
    is never used as the counter key directly (see `pseudonymous_key`)."""

    async def _dependency(
        request: Request,
        settings: Settings = Depends(get_settings_dep),
        limiter: RateLimiter = Depends(get_rate_limiter),
    ) -> None:
        raw_ip = request.client.host if request.client else "unknown"
        await _enforce_rate_limit(
            raw_identity=raw_ip,
            scope=scope,
            limit=limit,
            window_seconds=window_seconds,
            settings=settings,
            limiter=limiter,
        )

    return _dependency


def rate_limit_by_user(
    scope: str, *, limit: int, window_seconds: int
) -> Callable[..., Awaitable[None]]:
    """A FastAPI dependency limiting requests per authenticated user — for endpoints
    that dispatch expensive work (report generation, PDF rendering) an attacker with
    one valid session could otherwise hammer."""

    async def _dependency(
        user: User = Depends(get_current_user),
        settings: Settings = Depends(get_settings_dep),
        limiter: RateLimiter = Depends(get_rate_limiter),
    ) -> None:
        await _enforce_rate_limit(
            raw_identity=str(user.id),
            scope=scope,
            limit=limit,
            window_seconds=window_seconds,
            settings=settings,
            limiter=limiter,
        )

    return _dependency


async def get_current_session(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias="numra_session"),
) -> SessionModel:
    if not session_token:
        raise NotAuthenticated("no session cookie")
    token_hash = hash_session_token(session_token)
    session = await get_active_session_by_token_hash(
        db, token_hash=token_hash, now=dt.datetime.now(dt.UTC)
    )
    if session is None:
        raise NotAuthenticated("session not found, expired, or revoked")
    return session


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    session: SessionModel = Depends(get_current_session),
) -> User:
    user = await get_user_by_id(db, user_id=session.user_id)
    if user is None:
        raise NotAuthenticated("session user no longer exists")
    return user


def require_csrf(
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE_NAME),
    csrf_header: str | None = Header(default=None, alias=CSRF_HEADER_NAME),
) -> None:
    if not csrf_tokens_match(csrf_cookie, csrf_header):
        raise CsrfValidationFailed("missing or mismatched CSRF token")
