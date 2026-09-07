from __future__ import annotations

import datetime as dt
import re

import pytest
from httpx import ASGITransport, AsyncClient

from numra_api.app import create_app
from numra_api.auth.passwords import hash_password
from numra_api.auth.tokens import generate_token, hash_token
from numra_api.config import Settings
from numra_api.db import build_sessionmaker
from numra_api.repositories.users import create_user, get_user_by_email
from numra_api.repositories.verification_tokens import create_verification_token

pytestmark = pytest.mark.integration


async def _login(client, sessionmaker, email: str) -> dict:
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password("password12345"))
        await db.commit()
    response = await client.post(
        "/v1/auth/login", json={"email": email, "password": "password12345"}
    )
    assert response.status_code == 200
    return {"x-csrf-token": client.cookies["numra_csrf"]}


def _extract_token(body: str) -> str:
    match = re.search(r"token=([^\s]+)", body)
    assert match is not None, f"no token found in email body: {body!r}"
    return match.group(1)


async def test_request_email_verification_requires_auth(client) -> None:
    """CSRF is checked before authentication for this route (same dependency order as
    the pre-existing /v1/auth/change-password -- see routes/auth.py), so a request
    with a matching CSRF cookie/header pair but no session is what actually isolates
    the auth requirement; a completely bare request would fail CSRF first instead."""
    client.cookies.set("numra_csrf", "test-csrf-token")
    response = await client.post(
        "/v1/auth/request-email-verification", headers={"x-csrf-token": "test-csrf-token"}
    )
    assert response.status_code == 401


async def test_request_email_verification_requires_csrf(client, sessionmaker) -> None:
    await _login(client, sessionmaker, "no-csrf-verify@example.com")
    response = await client.post("/v1/auth/request-email-verification")
    assert response.status_code == 403


async def test_verify_email_successful_flow(client, sessionmaker, fake_email_sender) -> None:
    headers = await _login(client, sessionmaker, "verify-me@example.com")

    request_response = await client.post("/v1/auth/request-email-verification", headers=headers)
    assert request_response.status_code == 204
    assert len(fake_email_sender.sent) == 1
    assert fake_email_sender.sent[0]["to"] == "verify-me@example.com"
    token = _extract_token(fake_email_sender.sent[0]["body"])

    verify_response = await client.post("/v1/auth/verify-email", json={"token": token})
    assert verify_response.status_code == 204

    async with sessionmaker() as db:
        user = await get_user_by_email(db, email="verify-me@example.com")
        assert user.email_verified_at is not None


async def test_verify_email_single_use(client, sessionmaker, fake_email_sender) -> None:
    headers = await _login(client, sessionmaker, "single-use@example.com")
    await client.post("/v1/auth/request-email-verification", headers=headers)
    token = _extract_token(fake_email_sender.sent[0]["body"])

    first = await client.post("/v1/auth/verify-email", json={"token": token})
    assert first.status_code == 204

    second = await client.post("/v1/auth/verify-email", json={"token": token})
    assert second.status_code == 400
    assert second.json()["code"] == "INVALID_OR_EXPIRED_TOKEN"


async def test_verify_email_unknown_token_rejected(client) -> None:
    response = await client.post("/v1/auth/verify-email", json={"token": "not-a-real-token"})
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_OR_EXPIRED_TOKEN"


async def test_verify_email_expired_token_rejected_with_same_error(client, sessionmaker) -> None:
    async with sessionmaker() as db:
        user = await create_user(
            db, email="expired-verify@example.com", password_hash=hash_password("password12345")
        )
        raw_token = generate_token()
        await create_verification_token(
            db,
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=dt.datetime.now(dt.UTC) - dt.timedelta(hours=1),
        )
        await db.commit()

    response = await client.post("/v1/auth/verify-email", json={"token": raw_token})
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_OR_EXPIRED_TOKEN"


async def test_request_email_verification_invalidates_previous_token(
    client, sessionmaker, fake_email_sender
) -> None:
    headers = await _login(client, sessionmaker, "reissue@example.com")

    await client.post("/v1/auth/request-email-verification", headers=headers)
    old_token = _extract_token(fake_email_sender.sent[0]["body"])

    await client.post("/v1/auth/request-email-verification", headers=headers)
    new_token = _extract_token(fake_email_sender.sent[1]["body"])
    assert old_token != new_token

    old_attempt = await client.post("/v1/auth/verify-email", json={"token": old_token})
    assert old_attempt.status_code == 400
    assert old_attempt.json()["code"] == "INVALID_OR_EXPIRED_TOKEN"

    new_attempt = await client.post("/v1/auth/verify-email", json={"token": new_token})
    assert new_attempt.status_code == 204


async def test_request_email_verification_is_rate_limited(client, sessionmaker) -> None:
    headers = await _login(client, sessionmaker, "rate-limited-verify@example.com")

    for _ in range(5):
        response = await client.post("/v1/auth/request-email-verification", headers=headers)
        assert response.status_code == 204

    blocked = await client.post("/v1/auth/request-email-verification", headers=headers)
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "RATE_LIMIT_EXCEEDED"


async def test_request_email_verification_with_disabled_backend_is_503_not_500(
    settings: Settings, db_engine
) -> None:
    """Regression: unlike forgot-password, this route is authenticated -- there is no
    enumeration concern -- so `EmailDeliveryUnavailable` from a real (not faked)
    `DisabledEmailSender` (EMAIL_BACKEND=disabled) is allowed to reach the caller, but
    MUST be translated by app.py's central ApplicationError handler into a clean 503,
    never an unhandled 500. Deliberately bypasses the `app`/`client` fixtures --
    those always overwrite `state.email_sender` with `FakeEmailSender`."""
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
            db, email="disabled-backend-verify@example.com", password_hash=hash_password("x" * 12)
        )
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        login_response = await c.post(
            "/v1/auth/login",
            json={"email": "disabled-backend-verify@example.com", "password": "x" * 12},
        )
        assert login_response.status_code == 200
        response = await c.post(
            "/v1/auth/request-email-verification",
            headers={"x-csrf-token": c.cookies["numra_csrf"]},
        )

    assert response.status_code == 503
    assert response.json()["code"] == "EMAIL_DELIVERY_UNAVAILABLE"
