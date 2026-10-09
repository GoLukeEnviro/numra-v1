from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from numra_api.app import create_app
from numra_api.auth.passwords import hash_password
from numra_api.config import Settings
from numra_api.db import build_sessionmaker
from numra_api.models import AdminAuditEvent, User
from numra_api.models.enums import AuditAction
from numra_api.repositories.users import create_user
from numra_api.services.age_declaration import AGE_DECLARATION_VERSION

pytestmark = pytest.mark.integration

PASSWORD = "long-enough-password"


def _open_signup_client(settings: Settings, db_engine) -> AsyncClient:
    """Eigene App mit ALLOW_SELF_SIGNUP=true (der geteilte `client` hat den Default false)."""
    app = create_app(
        settings=Settings(
            database_url=settings.database_url, environment="test", allow_self_signup=True
        )
    )
    app.state.engine = db_engine
    app.state.sessionmaker = build_sessionmaker(db_engine)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _user_by_email(db_engine, email: str) -> User | None:
    async with build_sessionmaker(db_engine)() as db:
        return (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()


async def _age_audit_events(db_engine) -> list[AdminAuditEvent]:
    async with build_sessionmaker(db_engine)() as db:
        rows = await db.execute(
            select(AdminAuditEvent).where(AdminAuditEvent.action == str(AuditAction.AGE_CONFIRMED))
        )
        return list(rows.scalars())


async def _login_legacy_user(client, sessionmaker, email: str) -> None:
    """Bestandskonto: ohne Alterserklaerung angelegt (Spalten NULL), dann eingeloggt."""
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password(PASSWORD))
        await db.commit()
    response = await client.post("/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200


def _csrf(client) -> dict[str, str]:
    return {"x-csrf-token": client.cookies["numra_csrf"]}


@pytest.mark.parametrize(
    "extra",
    [{}, {"age_confirmed": False}, {"age_confirmed": None}, {"age_confirmed": "true"}],
    ids=["missing", "false", "null", "string-true"],
)
async def test_register_without_valid_age_confirmation_is_rejected(
    settings: Settings, db_engine, extra
) -> None:
    """Direktaufruf der API ohne UI: nur ein echtes JSON-`true` zaehlt."""
    async with _open_signup_client(settings, db_engine) as signup_client:
        response = await signup_client.post(
            "/v1/auth/register",
            json={"email": "direct@example.com", "password": PASSWORD, **extra},
        )

    assert response.status_code == 422
    assert "numra_session" not in response.cookies
    assert await _user_by_email(db_engine, "direct@example.com") is None
    assert await _age_audit_events(db_engine) == []


async def test_register_missing_flag_returns_clear_error_code(
    settings: Settings, db_engine
) -> None:
    async with _open_signup_client(settings, db_engine) as signup_client:
        response = await signup_client.post(
            "/v1/auth/register", json={"email": "direct@example.com", "password": PASSWORD}
        )

    assert response.status_code == 422
    assert response.json()["code"] == "AGE_CONFIRMATION_REQUIRED"


async def test_register_false_flag_returns_clear_error_code(settings: Settings, db_engine) -> None:
    async with _open_signup_client(settings, db_engine) as signup_client:
        response = await signup_client.post(
            "/v1/auth/register",
            json={"email": "direct@example.com", "password": PASSWORD, "age_confirmed": False},
        )

    assert response.status_code == 422
    assert response.json()["code"] == "AGE_CONFIRMATION_REQUIRED"


async def test_register_with_age_confirmation_stores_timestamp_version_and_audit(
    settings: Settings, db_engine
) -> None:
    before = dt.datetime.now(dt.UTC)
    async with _open_signup_client(settings, db_engine) as signup_client:
        response = await signup_client.post(
            "/v1/auth/register",
            json={"email": "adult@example.com", "password": PASSWORD, "age_confirmed": True},
        )
        me = await signup_client.get("/v1/auth/me")
    after = dt.datetime.now(dt.UTC)

    assert response.status_code == 201
    body = response.json()
    assert body["age_declaration_version"] == AGE_DECLARATION_VERSION == "age-declaration-v1"
    confirmed_at = dt.datetime.fromisoformat(body["age_confirmed_at"])
    assert confirmed_at.tzinfo is not None
    assert before <= confirmed_at <= after
    assert me.json()["age_confirmed_at"] == body["age_confirmed_at"]

    user = await _user_by_email(db_engine, "adult@example.com")
    assert user is not None
    assert user.age_confirmed_at is not None
    assert user.age_declaration_version == AGE_DECLARATION_VERSION

    events = await _age_audit_events(db_engine)
    assert len(events) == 1
    assert events[0].actor_user_id == user.id
    assert events[0].target_user_id == user.id
    assert events[0].safe_metadata == {
        "declaration_version": AGE_DECLARATION_VERSION,
        "source": "registration",
    }


async def test_legacy_account_is_unconfirmed_and_not_locked_out(client, sessionmaker) -> None:
    await _login_legacy_user(client, sessionmaker, "legacy@example.com")

    me = await client.get("/v1/auth/me")

    assert me.status_code == 200
    assert me.json()["age_confirmed_at"] is None
    assert me.json()["age_declaration_version"] is None


async def test_confirm_age_for_legacy_account_sets_values_and_audits(
    client, sessionmaker, db_engine
) -> None:
    await _login_legacy_user(client, sessionmaker, "legacy@example.com")

    response = await client.post(
        "/v1/auth/confirm-age", json={"age_confirmed": True}, headers=_csrf(client)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["age_confirmed_at"] is not None
    assert body["age_declaration_version"] == AGE_DECLARATION_VERSION
    assert (await client.get("/v1/auth/me")).json()["age_confirmed_at"] == body["age_confirmed_at"]
    events = await _age_audit_events(db_engine)
    assert [e.safe_metadata["source"] for e in events] == ["existing_account"]


async def test_confirm_age_is_idempotent(client, sessionmaker, db_engine) -> None:
    await _login_legacy_user(client, sessionmaker, "legacy@example.com")
    first = await client.post(
        "/v1/auth/confirm-age", json={"age_confirmed": True}, headers=_csrf(client)
    )

    second = await client.post(
        "/v1/auth/confirm-age", json={"age_confirmed": True}, headers=_csrf(client)
    )

    assert first.status_code == second.status_code == 200
    assert second.json()["age_confirmed_at"] == first.json()["age_confirmed_at"]
    assert len(await _age_audit_events(db_engine)) == 1


async def test_confirm_age_requires_explicit_true(client, sessionmaker) -> None:
    await _login_legacy_user(client, sessionmaker, "legacy@example.com")

    for payload in ({}, {"age_confirmed": False}):
        response = await client.post("/v1/auth/confirm-age", json=payload, headers=_csrf(client))
        assert response.status_code == 422
        assert response.json()["code"] == "AGE_CONFIRMATION_REQUIRED"
    assert (await client.get("/v1/auth/me")).json()["age_confirmed_at"] is None


async def test_confirm_age_rejects_extra_fields_such_as_birth_date(client, sessionmaker) -> None:
    await _login_legacy_user(client, sessionmaker, "legacy@example.com")

    response = await client.post(
        "/v1/auth/confirm-age",
        json={"age_confirmed": True, "birth_date": "1990-01-01"},
        headers=_csrf(client),
    )

    assert response.status_code == 422
    assert (await client.get("/v1/auth/me")).json()["age_confirmed_at"] is None


async def test_confirm_age_requires_authentication_and_csrf(client, sessionmaker) -> None:
    anonymous = await client.post("/v1/auth/confirm-age", json={"age_confirmed": True})
    assert anonymous.status_code in (401, 403)

    await _login_legacy_user(client, sessionmaker, "legacy@example.com")
    no_csrf = await client.post("/v1/auth/confirm-age", json={"age_confirmed": True})

    assert no_csrf.status_code == 403
    assert no_csrf.json()["code"] == "CSRF_VALIDATION_FAILED"
    assert (await client.get("/v1/auth/me")).json()["age_confirmed_at"] is None


def test_migration_chain_has_single_head_and_additive_nullable_columns() -> None:
    api_root = Path(__file__).resolve().parents[2]
    script = ScriptDirectory.from_config(Config(str(api_root / "alembic.ini")))
    assert len(script.get_heads()) == 1
    revision = script.get_revision("d2a8c4f6b1e3")
    assert revision is not None
    assert revision.down_revision == "c5a9d3e72b16"
    source = Path(revision.path).read_text(encoding="utf-8")
    assert "nullable=True" in source
    assert "nullable=False" not in source
    assert "server_default" not in source
