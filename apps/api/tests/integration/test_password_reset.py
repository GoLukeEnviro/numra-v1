from __future__ import annotations

import datetime as dt
import re

import pytest
from httpx import ASGITransport, AsyncClient

from numra_api.app import create_app
from numra_api.auth.passwords import hash_password
from numra_api.auth.sessions import generate_session_token, hash_session_token
from numra_api.auth.tokens import generate_token, hash_token
from numra_api.config import Settings
from numra_api.db import build_sessionmaker
from numra_api.repositories.password_reset_tokens import create_password_reset_token
from numra_api.repositories.sessions import create_session, list_active_sessions_for_user
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration


def _extract_token(body: str) -> str:
    match = re.search(r"token=([^\s]+)", body)
    assert match is not None, f"no token found in email body: {body!r}"
    return match.group(1)


async def test_forgot_password_anti_enumeration(client, sessionmaker) -> None:
    async with sessionmaker() as db:
        await create_user(
            db, email="known-reset@example.com", password_hash=hash_password("password12345")
        )
        await db.commit()

    known_response = await client.post(
        "/v1/auth/forgot-password", json={"email": "known-reset@example.com"}
    )
    unknown_response = await client.post(
        "/v1/auth/forgot-password", json={"email": "nobody-here@example.com"}
    )

    # Anti-enumeration: identical status and body regardless of whether the address
    # belongs to an account (the body itself is FastAPI's standard `null` for a
    # no-content 202 -- what matters is the two responses being indistinguishable).
    assert known_response.status_code == unknown_response.status_code == 202
    assert known_response.text == unknown_response.text


async def test_forgot_password_only_sends_for_existing_account(
    client, sessionmaker, fake_email_sender
) -> None:
    async with sessionmaker() as db:
        await create_user(
            db, email="gets-email@example.com", password_hash=hash_password("password12345")
        )
        await db.commit()

    await client.post("/v1/auth/forgot-password", json={"email": "gets-email@example.com"})
    await client.post("/v1/auth/forgot-password", json={"email": "no-such-account@example.com"})

    assert len(fake_email_sender.sent) == 1
    assert fake_email_sender.sent[0]["to"] == "gets-email@example.com"


async def test_reset_password_successful_flow_and_new_password_works(
    client, sessionmaker, fake_email_sender
) -> None:
    async with sessionmaker() as db:
        await create_user(
            db, email="reset-flow@example.com", password_hash=hash_password("old-password-123")
        )
        await db.commit()

    await client.post("/v1/auth/forgot-password", json={"email": "reset-flow@example.com"})
    token = _extract_token(fake_email_sender.sent[0]["body"])

    reset_response = await client.post(
        "/v1/auth/reset-password", json={"token": token, "new_password": "brand-new-password-1"}
    )
    assert reset_response.status_code == 204

    old_login = await client.post(
        "/v1/auth/login",
        json={"email": "reset-flow@example.com", "password": "old-password-123"},
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/v1/auth/login",
        json={"email": "reset-flow@example.com", "password": "brand-new-password-1"},
    )
    assert new_login.status_code == 200


async def test_reset_password_revokes_all_existing_sessions(
    client, sessionmaker, fake_email_sender
) -> None:
    """At least two active sessions ("devices") before the reset -- both must be
    revoked, not just the one that triggered the reset (there is no "caller's own
    session" here at all, unlike change-password -- see routes/auth.py)."""
    async with sessionmaker() as db:
        user = await create_user(
            db, email="multi-device@example.com", password_hash=hash_password("old-password-123")
        )
        now = dt.datetime.now(dt.UTC)
        await create_session(
            db,
            user_id=user.id,
            token_hash=hash_session_token(generate_session_token()),
            expires_at=now + dt.timedelta(hours=1),
        )
        await create_session(
            db,
            user_id=user.id,
            token_hash=hash_session_token(generate_session_token()),
            expires_at=now + dt.timedelta(hours=1),
        )
        await db.commit()
        user_id = user.id

    async with sessionmaker() as db:
        active_before = await list_active_sessions_for_user(
            db, user_id=user_id, now=dt.datetime.now(dt.UTC)
        )
        assert len(active_before) == 2

    await client.post("/v1/auth/forgot-password", json={"email": "multi-device@example.com"})
    token = _extract_token(fake_email_sender.sent[0]["body"])
    reset_response = await client.post(
        "/v1/auth/reset-password", json={"token": token, "new_password": "brand-new-password-1"}
    )
    assert reset_response.status_code == 204

    async with sessionmaker() as db:
        active_after = await list_active_sessions_for_user(
            db, user_id=user_id, now=dt.datetime.now(dt.UTC)
        )
        assert active_after == []


async def test_reset_password_invalid_or_expired_token(client, sessionmaker) -> None:
    async with sessionmaker() as db:
        user = await create_user(
            db, email="expired-reset@example.com", password_hash=hash_password("old-password-123")
        )
        raw_token = generate_token()
        await create_password_reset_token(
            db,
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=1),
        )
        await db.commit()

    response = await client.post(
        "/v1/auth/reset-password", json={"token": raw_token, "new_password": "brand-new-password-1"}
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_OR_EXPIRED_TOKEN"

    unknown_response = await client.post(
        "/v1/auth/reset-password",
        json={"token": "totally-made-up", "new_password": "brand-new-password-1"},
    )
    assert unknown_response.status_code == 400
    assert unknown_response.json()["code"] == "INVALID_OR_EXPIRED_TOKEN"


async def test_forgot_password_invalidates_previous_reset_token(
    client, sessionmaker, fake_email_sender
) -> None:
    async with sessionmaker() as db:
        await create_user(
            db, email="reissue-reset@example.com", password_hash=hash_password("old-password-123")
        )
        await db.commit()

    await client.post("/v1/auth/forgot-password", json={"email": "reissue-reset@example.com"})
    old_token = _extract_token(fake_email_sender.sent[0]["body"])

    await client.post("/v1/auth/forgot-password", json={"email": "reissue-reset@example.com"})
    new_token = _extract_token(fake_email_sender.sent[1]["body"])
    assert old_token != new_token

    old_attempt = await client.post(
        "/v1/auth/reset-password", json={"token": old_token, "new_password": "brand-new-password-1"}
    )
    assert old_attempt.status_code == 400
    assert old_attempt.json()["code"] == "INVALID_OR_EXPIRED_TOKEN"

    new_attempt = await client.post(
        "/v1/auth/reset-password", json={"token": new_token, "new_password": "brand-new-password-1"}
    )
    assert new_attempt.status_code == 204


async def test_forgot_password_is_rate_limited(client) -> None:
    for _ in range(5):
        response = await client.post(
            "/v1/auth/forgot-password", json={"email": "whoever@example.com"}
        )
        assert response.status_code == 202

    blocked = await client.post("/v1/auth/forgot-password", json={"email": "whoever@example.com"})
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "RATE_LIMIT_EXCEEDED"


async def test_reset_password_is_rate_limited(client) -> None:
    for _ in range(10):
        response = await client.post(
            "/v1/auth/reset-password",
            json={"token": "irrelevant", "new_password": "brand-new-password-1"},
        )
        assert response.status_code == 400

    blocked = await client.post(
        "/v1/auth/reset-password",
        json={"token": "irrelevant", "new_password": "brand-new-password-1"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "RATE_LIMIT_EXCEEDED"


async def test_reset_password_link_uses_configured_web_app_base_url(
    settings: Settings, db_engine
) -> None:
    """Regression: the reset-password link (auth_recovery_service.py's
    `build_web_app_url()` call) must be built from `settings.web_app_base_url` --
    with a distinct configured origin here, the real /reset-password path, and the
    token carried through unchanged -- never a hardcoded/guessed origin."""
    custom_settings = Settings(
        database_url=settings.database_url,
        environment="test",
        web_app_base_url="https://app.example.org",
    )
    app = create_app(settings=custom_settings)
    app.state.engine = db_engine
    app.state.sessionmaker = build_sessionmaker(db_engine)
    sent: list[dict] = []

    class _CapturingEmailSender:
        async def send(
            self, *, to: str, subject: str, body: str, html_body: str | None = None
        ) -> None:
            sent.append({"to": to, "subject": subject, "body": body, "html_body": html_body})

    app.state.email_sender = _CapturingEmailSender()

    async with app.state.sessionmaker() as db:
        await create_user(
            db, email="reset-origin@example.com", password_hash=hash_password("x" * 12)
        )
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        response = await c.post(
            "/v1/auth/forgot-password", json={"email": "reset-origin@example.com"}
        )

    assert response.status_code == 202
    assert len(sent) == 1
    token = _extract_token(sent[0]["body"])
    expected_link = f"https://app.example.org/reset-password?token={token}"
    assert expected_link in sent[0]["body"]
    assert expected_link in sent[0]["html_body"]


async def test_forgot_password_stays_anti_enumeration_safe_with_real_disabled_sender(
    settings: Settings, db_engine
) -> None:
    """Regression: with EMAIL_BACKEND=disabled (the documented production default
    until a real provider exists -- see config.py), `DisabledEmailSender.send` raises
    `EmailDeliveryUnavailable` for every call. Before this fix that propagated past
    forgot-password unhandled, turning "202" vs "an error" into a 100%-reliable
    enumeration oracle for exactly the accounts that *do* exist. Deliberately bypasses
    the `app`/`client` fixtures -- those always overwrite `state.email_sender` with
    `FakeEmailSender`, so only building the app directly here exercises the real
    `DisabledEmailSender` wiring from create_app()/build_email_sender()."""
    disabled_settings = Settings(
        database_url=settings.database_url,
        environment="test",
        email_backend="disabled",
    )
    app = create_app(settings=disabled_settings)
    app.state.engine = db_engine
    app.state.sessionmaker = build_sessionmaker(db_engine)

    async with app.state.sessionmaker() as db:
        await create_user(
            db, email="real-disabled-sender@example.com", password_hash=hash_password("x" * 12)
        )
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        known_response = await c.post(
            "/v1/auth/forgot-password", json={"email": "real-disabled-sender@example.com"}
        )
        unknown_response = await c.post(
            "/v1/auth/forgot-password", json={"email": "nobody-real-disabled@example.com"}
        )

    assert known_response.status_code == unknown_response.status_code == 202
    assert known_response.text == unknown_response.text
