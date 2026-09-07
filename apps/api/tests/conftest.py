from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from numra_api.app import create_app
from numra_api.config import Settings
from numra_api.db import build_engine, build_sessionmaker
from numra_api.email.sender import EmailSender
from numra_api.models import Base, EntitlementSet
from numra_api.repositories.entitlements import DEFAULT_ENTITLEMENT_SET_KEY
from numra_api.services.llm_factory import build_llm_provider
from numra_interpretation.llm.types import LLMProvider

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://numra:numra_dev_password@127.0.0.1:5432/numra_test",
)
#: A real (not mocked) apps/pdf instance, started separately for the test run (see
#: specs/evidence -- CI/local dev starts one on this port/token). Tests that need PDF
#: rendering exercise it for real; if it isn't reachable those specific tests fail with
#: a clear connection error rather than silently skipping.
TEST_PDF_URL = os.environ.get("TEST_PDF_URL", "http://127.0.0.1:4300")
TEST_PDF_TOKEN = os.environ.get("TEST_PDF_TOKEN", "test-token")


@pytest_asyncio.fixture
async def settings(tmp_path) -> Settings:
    # Tests opt into the mock provider explicitly (never relying on an implicit
    # default) — this is exactly the pattern production must never fall back to.
    return Settings(
        database_url=TEST_DATABASE_URL,
        environment="test",
        numra_llm_provider="mock",
        pdf_internal_url=TEST_PDF_URL,
        pdf_internal_token=TEST_PDF_TOKEN,
        export_storage_dir=str(tmp_path / "exports"),
    )


@pytest_asyncio.fixture
async def db_engine(settings: Settings):
    engine = build_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    # Base.metadata.create_all (not Alembic) builds the test schema -- so, unlike a
    # real deployment, the "beta_default" EntitlementSet the migration seeds never
    # gets inserted on its own. Reproduce that one seed row here so
    # GET /v1/me/entitlements has the same fallback to resolve in tests as in
    # production (see repositories/entitlements.py).
    async with build_sessionmaker(engine)() as db:
        db.add(EntitlementSet(key=DEFAULT_ENTITLEMENT_SET_KEY))
        await db.commit()
    yield engine
    await engine.dispose()


class FakeEmailSender:
    """Test double implementing `EmailSender` -- collects every send() call instead of
    logging/dispatching anything, so a test can read back the verification/reset link
    it just triggered (the real `LoggingEmailSender` only logs; it hands nothing back
    to the caller). See services/auth_recovery_service.py for what gets sent."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, *, to: str, subject: str, body: str) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})


@pytest_asyncio.fixture
async def app(settings: Settings, db_engine):
    application = create_app(settings=settings)
    application.state.engine = db_engine
    application.state.sessionmaker = build_sessionmaker(db_engine)
    # create_app() already builds a real LoggingEmailSender onto application.state
    # from settings.email_backend, exactly like every other state-service (pdf_client,
    # export_storage) -- this fixture overrides that state attribute afterwards,
    # purely so tests can read back what was "sent" (see FakeEmailSender above).
    application.state.email_sender = FakeEmailSender()
    return application


@pytest_asyncio.fixture
async def fake_email_sender(app) -> EmailSender:
    return app.state.email_sender


@pytest_asyncio.fixture
async def sessionmaker(app):
    return app.state.sessionmaker


@pytest_asyncio.fixture
async def llm(settings: Settings) -> LLMProvider:
    """The provider tests use when driving the worker directly (`run_one_cycle`).
    Built via the same factory production uses, from the same `settings` fixture the
    app itself was created with (which sets `numra_llm_provider="mock"`) — so this
    exercises `build_llm_provider` itself rather than special-casing tests."""
    return build_llm_provider(settings)


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def lukas_payload() -> dict:
    return {
        "birth_first_names": "Lukas",
        "birth_last_name": "Springer",
        "birth_date": "1986-07-18",
        "birth_time": {"value": "06:00:00", "precision": "exact"},
        "birth_place": {"display_name": "Meerbusch", "country_code": "DE"},
    }
