"""Orchestrates the four token-driven account-recovery flows (V2): request/verify
email verification, and forgot/reset password. Routes stay thin (see routes/auth.py)
-- this is the one place that ties token generation/hashing (auth/tokens.py),
persistence (repositories/verification_tokens.py,
repositories/password_reset_tokens.py, repositories/users.py,
repositories/sessions.py) and email dispatch (email/sender.py) together for each flow.
"""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.auth.passwords import hash_password
from numra_api.auth.tokens import generate_token, hash_token
from numra_api.config import Settings
from numra_api.email.sender import EmailSender
from numra_api.models import User
from numra_api.repositories.password_reset_tokens import (
    claim_password_reset_token,
    create_password_reset_token,
    invalidate_active_password_reset_tokens_for_user,
)
from numra_api.repositories.sessions import revoke_all_sessions_for_user
from numra_api.repositories.users import (
    get_user_by_email,
    get_user_by_id,
    mark_email_verified,
    update_user_password,
)
from numra_api.repositories.verification_tokens import (
    claim_verification_token,
    create_verification_token,
    invalidate_active_verification_tokens_for_user,
)
from numra_api.services.errors import EmailDeliveryUnavailable, InvalidOrExpiredToken

logger = logging.getLogger(__name__)


async def request_email_verification(
    db: AsyncSession, *, user: User, settings: Settings, email_sender: EmailSender
) -> None:
    now = dt.datetime.now(dt.UTC)
    await invalidate_active_verification_tokens_for_user(db, user_id=user.id, now=now)
    token = generate_token()
    expires_at = now + dt.timedelta(hours=settings.email_verification_token_ttl_hours)
    await create_verification_token(
        db, user_id=user.id, token_hash=hash_token(token), expires_at=expires_at
    )
    link = f"{settings.web_app_base_url}/verify-email?token={token}"
    await email_sender.send(
        to=user.email,
        subject=f"Verify your {settings.app_brand_name} email address",
        body=f"Confirm your email address by opening this link: {link}",
    )


async def verify_email(db: AsyncSession, *, token: str) -> None:
    now = dt.datetime.now(dt.UTC)
    user_id = await claim_verification_token(db, token_hash=hash_token(token), now=now)
    if user_id is None:
        raise InvalidOrExpiredToken("email verification token is invalid, expired, or used")
    user = await get_user_by_id(db, user_id=user_id)
    if user is None:
        # The token's owning user was deleted between the claim and this lookup --
        # treat identically to any other invalid token rather than a 500.
        raise InvalidOrExpiredToken("email verification token is invalid, expired, or used")
    await mark_email_verified(db, user=user, verified_at=now)


async def forgot_password(
    db: AsyncSession, *, email: str, settings: Settings, email_sender: EmailSender
) -> None:
    """Always completes without raising -- routes/auth.py returns 202 regardless of
    whether `email` matches an account (anti-enumeration). Only sends anything, and
    only touches the database, when it does.

    Critically, this must stay true even when `email_sender.send` itself fails (e.g.
    `EmailDeliveryUnavailable` from `DisabledEmailSender` -- the documented production
    default until a real provider exists, see Settings.email_backend): letting that
    propagate would turn "202" vs "an unhandled error" into a HTTP-status
    enumeration oracle exactly as reliable as the thing this function exists to
    prevent. The reset token itself is still issued regardless -- only the outbound
    email is best-effort here."""
    user = await get_user_by_email(db, email=email)
    if user is None:
        return
    now = dt.datetime.now(dt.UTC)
    await invalidate_active_password_reset_tokens_for_user(db, user_id=user.id, now=now)
    token = generate_token()
    expires_at = now + dt.timedelta(minutes=settings.password_reset_token_ttl_minutes)
    await create_password_reset_token(
        db, user_id=user.id, token_hash=hash_token(token), expires_at=expires_at
    )
    link = f"{settings.web_app_base_url}/reset-password?token={token}"
    try:
        await email_sender.send(
            to=user.email,
            subject=f"Reset your {settings.app_brand_name} password",
            body=f"Reset your password by opening this link: {link}",
        )
    except EmailDeliveryUnavailable:
        logger.warning("password reset email could not be sent (EMAIL_BACKEND unavailable)")


async def reset_password(db: AsyncSession, *, token: str, new_password: str) -> None:
    now = dt.datetime.now(dt.UTC)
    user_id = await claim_password_reset_token(db, token_hash=hash_token(token), now=now)
    if user_id is None:
        raise InvalidOrExpiredToken("password reset token is invalid, expired, or used")
    user = await get_user_by_id(db, user_id=user_id)
    if user is None:
        raise InvalidOrExpiredToken("password reset token is invalid, expired, or used")
    await update_user_password(db, user=user, password_hash=hash_password(new_password))
    # Every session, not "every other" -- unlike change-password there is no
    # "caller's own current session" here (the caller was never authenticated).
    await revoke_all_sessions_for_user(db, user_id=user.id, now=now)
