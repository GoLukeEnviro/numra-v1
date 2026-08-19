from __future__ import annotations

import datetime as dt
from collections.abc import AsyncIterator

from fastapi import Cookie, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.auth.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, csrf_tokens_match
from numra_api.auth.sessions import hash_session_token
from numra_api.config import Settings
from numra_api.models import User
from numra_api.repositories.sessions import get_active_session_by_token_hash
from numra_api.repositories.users import get_user_by_id
from numra_api.services.errors import CsrfValidationFailed, NotAuthenticated
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


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias="numra_session"),
) -> User:
    if not session_token:
        raise NotAuthenticated("no session cookie")
    token_hash = hash_session_token(session_token)
    session = await get_active_session_by_token_hash(
        db, token_hash=token_hash, now=dt.datetime.now(dt.UTC)
    )
    if session is None:
        raise NotAuthenticated("session not found, expired, or revoked")
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
