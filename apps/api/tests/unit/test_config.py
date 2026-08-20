from __future__ import annotations

import pytest
from pydantic import ValidationError

from numra_api.config import Settings

pytestmark = pytest.mark.unit

_DB_URL = "postgresql+asyncpg://numra:numra_dev_password@127.0.0.1:5432/numra_test"


def test_mock_llm_provider_forbidden_in_production() -> None:
    with pytest.raises(ValidationError, match="NUMRA_LLM_PROVIDER=mock is not permitted"):
        Settings(database_url=_DB_URL, environment="production", numra_llm_provider="mock")


def test_mock_llm_provider_allowed_outside_production() -> None:
    Settings(database_url=_DB_URL, environment="test", numra_llm_provider="mock")  # must not raise


def test_disabled_and_ollama_llm_provider_allowed_in_production() -> None:
    # rate_limit_backend="redis" here only to isolate this test from the *other*
    # production validator (_forbid_memory_rate_limiter_in_production) -- not itself
    # what this test is about.
    Settings(
        database_url=_DB_URL,
        environment="production",
        numra_llm_provider="disabled",
        rate_limit_backend="redis",
        redis_url="redis://redis:6379/0",
    )
    Settings(
        database_url=_DB_URL,
        environment="production",
        numra_llm_provider="ollama",
        ollama_base_url="https://ollama.example.invalid",
        ollama_api_key="key",
        rate_limit_backend="redis",
        redis_url="redis://redis:6379/0",
    )


def test_memory_rate_limit_backend_forbidden_in_production() -> None:
    with pytest.raises(ValidationError, match="RATE_LIMIT_BACKEND=memory is not permitted"):
        Settings(database_url=_DB_URL, environment="production", rate_limit_backend="memory")


def test_memory_rate_limit_backend_allowed_outside_production() -> None:
    Settings(
        database_url=_DB_URL, environment="test", rate_limit_backend="memory"
    )  # must not raise


def test_redis_rate_limit_backend_allowed_in_production() -> None:
    Settings(
        database_url=_DB_URL,
        environment="production",
        rate_limit_backend="redis",
        redis_url="redis://redis:6379/0",
    )  # must not raise
