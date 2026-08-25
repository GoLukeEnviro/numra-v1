from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.auth.csrf import CSRF_COOKIE_NAME, generate_csrf_token
from numra_api.auth.passwords import hash_password, verify_password
from numra_api.auth.sessions import generate_session_token, hash_session_token
from numra_api.config import Settings
from numra_api.deps import (
    get_current_session,
    get_current_user,
    get_db,
    get_settings_dep,
    rate_limit_by_ip,
    rate_limit_by_user,
    require_csrf,
)
from numra_api.models import Session as SessionModel
from numra_api.models import User
from numra_api.repositories.sessions import (
    create_session,
    list_active_sessions_for_user,
    revoke_all_sessions_except,
    revoke_session,
)
from numra_api.repositories.users import create_user, get_user_by_email, update_user_password
from numra_api.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    SessionOut,
    UserOut,
)
from numra_api.services.errors import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    SelfSignupDisabled,
)

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _set_auth_cookies(
    response: Response, *, session_token: str, secure: bool, ttl_hours: int
) -> None:
    max_age = ttl_hours * 3600
    response.set_cookie(
        "numra_session",
        session_token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        generate_csrf_token(),
        max_age=max_age,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
    )


async def _issue_authenticated_session(
    *, response: Response, db: AsyncSession, settings: Settings, user: User
) -> None:
    """The one place a browser becomes signed in -- both `login` and `register` go
    through here so the two can never drift apart on TTL, hashing, or cookie flags."""
    token = generate_session_token()
    expires_at = dt.datetime.now(dt.UTC) + dt.timedelta(hours=settings.session_ttl_hours)
    await create_session(
        db, user_id=user.id, token_hash=hash_session_token(token), expires_at=expires_at
    )
    _set_auth_cookies(
        response,
        session_token=token,
        secure=settings.cookies_secure,
        ttl_hours=settings.session_ttl_hours,
    )


@router.post(
    "/register",
    response_model=UserOut,
    status_code=201,
    dependencies=[Depends(rate_limit_by_ip("auth:register", limit=5, window_seconds=3600))],
)
async def register(
    body: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> UserOut:
    """V1.6 B: a successful registration is signed in immediately (same cookies as
    `login`, no server-side redirect -- the client decides where to go next). Role and
    is_active come exclusively from the model defaults; `RegisterRequest`'s
    `extra="forbid"` is what stops a "role": "ADMIN" body from ever reaching here."""
    if not settings.allow_self_signup:
        raise SelfSignupDisabled("self-signup is disabled (ALLOW_SELF_SIGNUP=false)")
    if await get_user_by_email(db, email=body.email) is not None:
        raise EmailAlreadyRegistered("an account with this email already exists")

    try:
        user = await create_user(db, email=body.email, password_hash=hash_password(body.password))
    except IntegrityError as exc:
        # The check above loses to a concurrent signup for the same address; the unique
        # index on users.email is the only real arbiter, and losing that race must
        # surface as this application error, never as a raw driver exception.
        await db.rollback()
        raise EmailAlreadyRegistered("an account with this email already exists") from exc

    await _issue_authenticated_session(response=response, db=db, settings=settings, user=user)
    return UserOut(id=str(user.id), email=user.email, role=str(user.role), is_active=user.is_active)


@router.post(
    "/login",
    response_model=UserOut,
    dependencies=[Depends(rate_limit_by_ip("auth:login", limit=10, window_seconds=60))],
)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> UserOut:
    user = await get_user_by_email(db, email=body.email)
    if user is None or not verify_password(user.password_hash, body.password) or not user.is_active:
        # Deliberately identical error for wrong-password, unknown-email, and
        # disabled-account -- a disabled account must never be distinguishable from
        # a simple login failure (see get_current_user's matching anti-enumeration
        # behavior for the session path).
        raise InvalidCredentials("invalid email or password")

    await _issue_authenticated_session(response=response, db=db, settings=settings, user=user)
    return UserOut(id=str(user.id), email=user.email, role=str(user.role), is_active=user.is_active)


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf)])
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> None:
    token = request.cookies.get("numra_session")
    if token:
        await revoke_session(db, token_hash=hash_session_token(token), now=dt.datetime.now(dt.UTC))
    response.delete_cookie("numra_session", path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(id=str(user.id), email=user.email, role=str(user.role), is_active=user.is_active)


@router.post(
    "/change-password",
    status_code=204,
    dependencies=[
        Depends(require_csrf),
        Depends(rate_limit_by_user("auth:change_password", limit=5, window_seconds=3600)),
    ],
)
async def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    session: SessionModel = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> None:
    """V1.5 Epic N: requires the current password even though the caller already has
    a valid session (a left-open or hijacked session should not be enough on its
    own). On success every *other* active session for this user is revoked -- the
    caller's own session (the one making this request) stays valid, so they are not
    logged out by changing their own password."""
    if not verify_password(user.password_hash, body.current_password):
        raise InvalidCredentials("current password is incorrect")
    await update_user_password(db, user=user, password_hash=hash_password(body.new_password))
    await revoke_all_sessions_except(
        db, user_id=user.id, keep_token_hash=session.token_hash, now=dt.datetime.now(dt.UTC)
    )


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    user: User = Depends(get_current_user),
    session: SessionModel = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> list[SessionOut]:
    """V1.5 Epic N: every device/browser currently signed in as this user. No IP
    address or device identifier is stored anywhere (see models.tables.Session), so
    there is nothing to redact here beyond simply not having it."""
    sessions = await list_active_sessions_for_user(db, user_id=user.id, now=dt.datetime.now(dt.UTC))
    return [
        SessionOut(
            id=str(s.id),
            created_at=s.created_at,
            expires_at=s.expires_at,
            is_current=s.token_hash == session.token_hash,
        )
        for s in sessions
    ]


@router.post("/sessions/revoke-others", status_code=204, dependencies=[Depends(require_csrf)])
async def revoke_other_sessions(
    user: User = Depends(get_current_user),
    session: SessionModel = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> None:
    """V1.5 Epic N: "Log out other devices" -- revokes every active session for this
    user except the one making this request."""
    await revoke_all_sessions_except(
        db, user_id=user.id, keep_token_hash=session.token_hash, now=dt.datetime.now(dt.UTC)
    )
