from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from numra_api.app import create_app
from numra_api.config import Settings
from numra_api.db import build_engine, build_sessionmaker
from numra_api.models import Base

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://numra:numra_dev_password@127.0.0.1:5432/numra_test",
)


@pytest_asyncio.fixture
async def settings() -> Settings:
    return Settings(database_url=TEST_DATABASE_URL, environment="test")


@pytest_asyncio.fixture
async def db_engine(settings: Settings):
    engine = build_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def app(settings: Settings, db_engine):
    application = create_app(settings=settings)
    application.state.engine = db_engine
    application.state.sessionmaker = build_sessionmaker(db_engine)
    return application


@pytest_asyncio.fixture
async def sessionmaker(app):
    return app.state.sessionmaker


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
