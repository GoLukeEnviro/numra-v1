from __future__ import annotations

import pytest

from numra_api.auth.passwords import hash_password
from numra_api.cli import promote_admin
from numra_api.config import Settings
from numra_api.models.enums import UserRole
from numra_api.repositories.users import create_user, get_user_by_email

pytestmark = pytest.mark.integration


async def _seed_user(sessionmaker, email: str, password: str):
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password(password))
        await db.commit()


async def test_promote_admin_promotes_existing_user(
    sessionmaker, settings: Settings, monkeypatch
) -> None:
    """Calls the async CLI function directly against the test DB fixture (same
    pattern as `test_register_rejects_password_shorter_than_12_chars`'s direct-app
    construction) -- the CLI builds its own engine from `get_settings()`, so we make
    that resolve to the test database via monkeypatch."""
    await _seed_user(sessionmaker, "promote-me@example.com", "correct horse battery staple")

    monkeypatch.setattr("numra_api.cli.get_settings", lambda: settings)

    exit_code = await promote_admin("promote-me@example.com")
    assert exit_code == 0

    async with sessionmaker() as db:
        user = await get_user_by_email(db, email="promote-me@example.com")
        assert user.role == UserRole.ADMIN


async def test_promote_admin_is_idempotent(sessionmaker, settings: Settings, monkeypatch) -> None:
    await _seed_user(sessionmaker, "already-admin@example.com", "correct horse battery staple")
    monkeypatch.setattr("numra_api.cli.get_settings", lambda: settings)

    first = await promote_admin("already-admin@example.com")
    second = await promote_admin("already-admin@example.com")
    assert first == 0
    assert second == 0

    async with sessionmaker() as db:
        user = await get_user_by_email(db, email="already-admin@example.com")
        assert user.role == UserRole.ADMIN


async def test_promote_admin_does_not_create_user(
    sessionmaker, settings: Settings, monkeypatch
) -> None:
    monkeypatch.setattr("numra_api.cli.get_settings", lambda: settings)

    exit_code = await promote_admin("nonexistent@example.com")
    assert exit_code == 1

    async with sessionmaker() as db:
        user = await get_user_by_email(db, email="nonexistent@example.com")
        assert user is None


async def test_promote_admin_normalizes_email_case(
    sessionmaker, settings: Settings, monkeypatch
) -> None:
    await _seed_user(sessionmaker, "case-test@example.com", "correct horse battery staple")
    monkeypatch.setattr("numra_api.cli.get_settings", lambda: settings)

    exit_code = await promote_admin("  Case-Test@Example.com  ")
    assert exit_code == 0

    async with sessionmaker() as db:
        user = await get_user_by_email(db, email="case-test@example.com")
        assert user.role == UserRole.ADMIN
