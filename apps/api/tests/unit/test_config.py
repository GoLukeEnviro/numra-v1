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
    # rate_limit_backend="redis"/email_backend="disabled" here only to isolate this
    # test from the *other* production validators
    # (_forbid_memory_rate_limiter_in_production,
    # _forbid_logging_email_backend_in_production) -- not itself what this test is
    # about.
    Settings(
        database_url=_DB_URL,
        environment="production",
        numra_llm_provider="disabled",
        rate_limit_backend="redis",
        redis_url="redis://redis:6379/0",
        email_backend="disabled",
    )
    Settings(
        database_url=_DB_URL,
        environment="production",
        numra_llm_provider="ollama",
        ollama_base_url="https://ollama.example.invalid",
        ollama_api_key="key",
        rate_limit_backend="redis",
        redis_url="redis://redis:6379/0",
        email_backend="disabled",
    )


def test_memory_rate_limit_backend_forbidden_in_production() -> None:
    with pytest.raises(ValidationError, match="RATE_LIMIT_BACKEND=memory is not permitted"):
        Settings(
            database_url=_DB_URL,
            environment="production",
            rate_limit_backend="memory",
            email_backend="disabled",
        )


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
        email_backend="disabled",
    )  # must not raise


def test_logging_email_backend_forbidden_in_production() -> None:
    with pytest.raises(ValidationError, match="EMAIL_BACKEND=logging is not permitted"):
        Settings(
            database_url=_DB_URL,
            environment="production",
            email_backend="logging",
            rate_limit_backend="redis",
            redis_url="redis://redis:6379/0",
        )


def test_logging_email_backend_allowed_outside_production() -> None:
    Settings(database_url=_DB_URL, environment="test", email_backend="logging")  # must not raise


def test_disabled_email_backend_allowed_in_production() -> None:
    # "disabled" is the numra_llm_provider="disabled" analogue -- no real EmailSender
    # exists in V1 (see email/sender.py), so this is what a production deployment
    # configures until a real provider is added.
    Settings(
        database_url=_DB_URL,
        environment="production",
        email_backend="disabled",
        rate_limit_backend="redis",
        redis_url="redis://redis:6379/0",
    )  # must not raise
