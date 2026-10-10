from __future__ import annotations

import datetime as dt
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TypeVar

from fastapi import Cookie, Depends, Header, Request
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.auth.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, csrf_tokens_match
from numra_api.auth.sessions import hash_session_token
from numra_api.config import Settings
from numra_api.email.sender import EmailSender
from numra_api.models import Session as SessionModel
from numra_api.models import User
from numra_api.models.enums import UserRole
from numra_api.proxy_trust import rate_limit_identity
from numra_api.rate_limit import RateLimiter, pseudonymous_key
from numra_api.repositories.sessions import get_active_session_by_token_hash
from numra_api.repositories.users import get_user_by_id, normalize_email
from numra_api.services.errors import (
    CsrfValidationFailed,
    Forbidden,
    NotAuthenticated,
    RateLimitExceeded,
    RateLimitUnavailable,
)
from numra_api.services.feature_flag_cache import FeatureFlagCache
from numra_api.services.pdf_client import PdfServiceClient
from numra_api.storage.exports import ExportStorage
from numra_interpretation.llm.types import LLMProvider

_ci_diag_log = logging.getLogger("numra_api.ci_diag")
_rate_limit_log = logging.getLogger("numra_api.rate_limit")
T = TypeVar("T")


def _ci_diag_enabled(request: Request) -> bool:
    settings = getattr(request.app.state, "settings", None)
    return bool(settings is not None and settings.environment == "test")


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    sessionmaker = request.app.state.sessionmaker
    if not _ci_diag_enabled(request):
        async with sessionmaker() as session:
            yield session
            await session.commit()
        return

    # [CI-DIAG] -- only under ENVIRONMENT=test. Correlates each request's DB
    # transaction with the flaky "stale read straight after my own write" pattern:
    # logs the request, its backend xid just before COMMIT, and how long the COMMIT
    # itself took, so a follow-up read that misses a just-committed row can be
    # lined up against the exact commit that should have made it visible.
    corr = getattr(getattr(request, "state", None), "correlation_id", None)
    method, path = request.method, request.url.path
    async with sessionmaker() as session:
        yield session
        try:
            xid_row = await session.execute(text("SELECT txid_current()"))
            pre_commit_xid = xid_row.scalar_one()
        except Exception:  # pragma: no cover - diagnostics must never break a request
            pre_commit_xid = None
        started = time.perf_counter()
        await session.commit()
        commit_ms = round((time.perf_counter() - started) * 1000, 2)
        _ci_diag_log.info(
            "[CI-DIAG] db-commit",
            extra={
                "correlation_id": corr,
                "method": method,
                "path": path,
                "pre_commit_xid": pre_commit_xid,
                "commit_ms": commit_ms,
            },
        )


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_feature_flag_cache(request: Request) -> FeatureFlagCache:
    cache: FeatureFlagCache = request.app.state.feature_flag_cache
    return cache


def get_export_storage(request: Request) -> ExportStorage:
    storage: ExportStorage = request.app.state.export_storage
    return storage


def get_pdf_client(request: Request) -> PdfServiceClient:
    client: PdfServiceClient = request.app.state.pdf_client
    return client


def get_rate_limiter(request: Request) -> RateLimiter:
    limiter: RateLimiter = request.app.state.rate_limiter
    return limiter


def get_email_sender(request: Request) -> EmailSender:
    sender: EmailSender = request.app.state.email_sender
    return sender


def get_llm_provider(request: Request) -> LLMProvider:
    """PR-V2-09 -- the Copilot pipeline is the first surface that calls the LLM
    synchronously inside a route (interactive chat latency, no job/worker, unlike
    report/relationship-analysis generation which only ever runs inside
    analysis_worker.py). Built once in `app.py::create_app` via the same
    `services.llm_factory.build_llm_provider` factory every other caller uses."""
    provider: LLMProvider = request.app.state.llm_provider
    return provider


def client_ip_of(request: Request) -> str:
    """Vertrauenswürdig ermittelte Client-IP (siehe ProxyTrustMiddleware); ohne
    Middleware-Ergebnis die rohe Peer-Adresse. Nie aus Request-Headern gelesen."""
    ip = request.scope.get("state", {}).get("client_ip")
    if isinstance(ip, str):
        return ip
    return request.client.host if request.client else "unknown"


async def _enforce_rate_limit(
    *,
    raw_identity: str,
    scope: str,
    limit: int | None,
    window_seconds: int | None,
    settings: Settings,
    limiter: RateLimiter,
) -> None:
    """`limit`/`window_seconds` None = benannte Policy `scope` (Default oder Override
    aus `RATE_LIMIT_OVERRIDES`, siehe rate_limit/policies.py).

    Backend-Ausfall (Redis nicht erreichbar): fail-closed mit 503 RATE_LIMIT_UNAVAILABLE.
    Ein ausgefallener Zähler darf Login-/Reset-Versuche und kostenintensive Endpunkte
    nicht unbegrenzt freigeben (vorher: ungefangene Exception -> 500, ebenfalls gesperrt)."""
    if limit is None or window_seconds is None:
        limit, window_seconds = settings.rate_limit_policy(scope)
    key = f"{scope}:{pseudonymous_key(raw_identity, secret=settings.session_secret)}"
    result = await _limiter_call(
        scope, limiter.check(key=key, limit=limit, window_seconds=window_seconds)
    )
    if not result.allowed:
        raise RateLimitExceeded(retry_after_seconds=result.retry_after_seconds)


def rate_limit_by_ip(
    scope: str, *, limit: int | None = None, window_seconds: int | None = None
) -> Callable[..., Awaitable[None]]:
    """A FastAPI dependency limiting requests per client IP — for unauthenticated
    endpoints (login, register) where there is no user id yet to key on. The IP is the
    trusted one from `client_ip_of` (never a free-form header) and is never used as the
    counter key directly (see `pseudonymous_key`). Without explicit `limit`/
    `window_seconds`, `scope` names a configurable policy."""

    async def _dependency(
        request: Request,
        settings: Settings = Depends(get_settings_dep),
        limiter: RateLimiter = Depends(get_rate_limiter),
    ) -> None:
        await _enforce_rate_limit(
            raw_identity=rate_limit_identity(client_ip_of(request)),
            scope=scope,
            limit=limit,
            window_seconds=window_seconds,
            settings=settings,
            limiter=limiter,
        )

    return _dependency


def rate_limit_by_user(
    scope: str, *, limit: int | None = None, window_seconds: int | None = None
) -> Callable[..., Awaitable[None]]:
    """A FastAPI dependency limiting requests per authenticated user — for endpoints
    that dispatch expensive work (report generation, PDF rendering) an attacker with
    one valid session could otherwise hammer. The key is `user.id` from the server-side
    session, never a header. Without explicit `limit`/`window_seconds`, `scope` names a
    configurable policy."""

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


def _target_args(request: Request, policy: str, target: str) -> dict[str, object]:
    settings: Settings = request.app.state.settings
    limit, window_seconds = settings.rate_limit_policy(policy)
    secret = settings.session_secret
    return {
        "key": f"{policy}:{pseudonymous_key(normalize_email(target), secret=secret)}",
        "limit": limit,
        "window_seconds": window_seconds,
    }


async def _limiter_call(scope: str, call: Awaitable[T]) -> T:
    try:
        return await call
    except (RedisError, OSError):
        _rate_limit_log.error("rate limiter backend unavailable (scope=%s)", scope)
        raise RateLimitUnavailable("rate limiter unavailable") from None


async def enforce_target_rate_limit(request: Request, *, policy: str, target: str) -> None:
    """Count every attempt per target address (normalised e-mail), called at the top of a
    handler once the body is parsed. Applied identically whether or not an account
    exists, so neither the limit nor its error reveals which addresses are registered."""
    await _enforce_rate_limit(
        raw_identity=normalize_email(target),
        scope=policy,
        limit=None,
        window_seconds=None,
        settings=request.app.state.settings,
        limiter=request.app.state.rate_limiter,
    )


async def clear_target_failures(request: Request, *, policy: str, target: str) -> None:
    """Failure-only counters, step 3: a successful login resets the target's counter."""
    key = str(_target_args(request, policy, target)["key"])
    await _limiter_call(policy, request.app.state.rate_limiter.reset(key=key))


async def get_current_session(
    request: Request,
    db: AsyncSession = Depends(get_db, scope="function"),
    settings: Settings = Depends(get_settings_dep),
) -> SessionModel:
    # Read via `settings.session_cookie_name` rather than a Cookie(alias=...) default:
    # that alias is bound at import time, so it can never reflect a per-app (e.g.
    # per-test) Settings override the way `request.app.state.settings` can.
    session_token = request.cookies.get(settings.session_cookie_name)
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
    db: AsyncSession = Depends(get_db, scope="function"),
    session: SessionModel = Depends(get_current_session),
) -> User:
    user = await get_user_by_id(db, user_id=session.user_id)
    if user is None or not user.is_active:
        # Deliberately indistinguishable from "no session" -- a disabled account must
        # never be enumerable via a different error shape than "not authenticated".
        raise NotAuthenticated("session user no longer exists")
    return user


async def get_current_bearer_session(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> SessionModel:
    """Resolve a non-ambient native credential without changing browser auth."""
    if not authorization:
        raise NotAuthenticated("no bearer token")
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip() or " " in token.strip():
        raise NotAuthenticated("malformed bearer token")
    session = await get_active_session_by_token_hash(
        db, token_hash=hash_session_token(token.strip()), now=dt.datetime.now(dt.UTC)
    )
    if session is None:
        raise NotAuthenticated("session not found, expired, or revoked")
    return session


async def get_current_bearer_user(
    db: AsyncSession = Depends(get_db, scope="function"),
    session: SessionModel = Depends(get_current_bearer_session),
) -> User:
    user = await get_user_by_id(db, user_id=session.user_id)
    if user is None or not user.is_active:
        raise NotAuthenticated("session user no longer exists")
    return user


async def get_current_user_any_auth(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db, scope="function"),
    settings: Settings = Depends(get_settings_dep),
) -> User:
    """Accept either credential on a read-only route the native app shares with the
    browser (MOBILE-12C). The presence of an `Authorization` header — not its validity
    — selects the bearer path, so a native client never silently falls back to an
    ambient cookie and a broken token still fails loudly with the generic 401.

    Both branches delegate to the existing resolvers rather than repeating the session
    lookup, which is why ownership, revocation and the disabled-account behaviour stay
    byte-identical to the cookie-only routes."""
    if authorization is not None:
        bearer_session = await get_current_bearer_session(authorization=authorization, db=db)
        return await get_current_bearer_user(db=db, session=bearer_session)
    cookie_session = await get_current_session(request=request, db=db, settings=settings)
    return await get_current_user(db=db, session=cookie_session)


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Admin-only gate. `is_active` is already guaranteed by the composed
    `get_current_user` above -- this only adds the role check."""
    if user.role != UserRole.ADMIN:
        raise Forbidden("admin role required")
    return user


def require_csrf(
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE_NAME),
    csrf_header: str | None = Header(default=None, alias=CSRF_HEADER_NAME),
) -> None:
    if not csrf_tokens_match(csrf_cookie, csrf_header):
        raise CsrfValidationFailed("missing or mismatched CSRF token")
