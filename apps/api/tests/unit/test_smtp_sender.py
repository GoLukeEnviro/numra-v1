from __future__ import annotations

from unittest.mock import AsyncMock

import aiosmtplib
import pytest

from numra_api.config import Settings
from numra_api.email.smtp_sender import SmtpEmailSender
from numra_api.services.errors import (
    SmtpAuthenticationError,
    SmtpConfigurationError,
    SmtpConnectionError,
    SmtpTimeoutError,
)

pytestmark = pytest.mark.unit

_DB_URL = "postgresql+asyncpg://numra:numra_dev_password@127.0.0.1:5432/numra_test"


def _smtp_settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "database_url": _DB_URL,
        "environment": "test",
        "email_backend": "smtp",
        "smtp_host": "smtp.example.invalid",
        "smtp_port": 587,
        "smtp_from_email": "no-reply@example.invalid",
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


async def test_send_dispatches_via_aiosmtplib(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_send = AsyncMock(return_value=({}, "OK"))
    monkeypatch.setattr(aiosmtplib, "send", mock_send)
    sender = SmtpEmailSender(_smtp_settings(smtp_username="user", smtp_password="pw"))

    await sender.send(to="a@example.com", subject="Hi", body="plain", html_body="<p>hi</p>")

    assert mock_send.await_count == 1
    _, kwargs = mock_send.call_args
    assert kwargs["hostname"] == "smtp.example.invalid"
    assert kwargs["port"] == 587
    assert kwargs["username"] == "user"
    assert kwargs["password"] == "pw"  # unwrapped from SecretStr only for this call


async def test_send_never_logs_or_raises_with_password_in_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        aiosmtplib, "send", AsyncMock(side_effect=aiosmtplib.SMTPAuthenticationError(535, "no"))
    )
    sender = SmtpEmailSender(_smtp_settings(smtp_username="user", smtp_password="super-secret"))

    with pytest.raises(SmtpAuthenticationError) as exc_info:
        await sender.send(to="a@example.com", subject="Hi", body="plain")

    assert "super-secret" not in str(exc_info.value)


async def test_send_wraps_timeout_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        aiosmtplib, "send", AsyncMock(side_effect=aiosmtplib.SMTPConnectTimeoutError("timed out"))
    )
    sender = SmtpEmailSender(_smtp_settings())

    with pytest.raises(SmtpTimeoutError):
        await sender.send(to="a@example.com", subject="Hi", body="plain")


async def test_send_wraps_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        aiosmtplib, "send", AsyncMock(side_effect=aiosmtplib.SMTPConnectError("refused"))
    )
    sender = SmtpEmailSender(_smtp_settings())

    with pytest.raises(SmtpConnectionError):
        await sender.send(to="a@example.com", subject="Hi", body="plain")


async def test_send_raises_configuration_error_when_host_missing() -> None:
    settings = _smtp_settings(smtp_host=None)
    sender = SmtpEmailSender(settings)

    with pytest.raises(SmtpConfigurationError):
        await sender.send(to="a@example.com", subject="Hi", body="plain")


def test_starttls_and_use_tls_both_true_is_rejected_at_settings_construction() -> None:
    with pytest.raises(Exception, match="SMTP_STARTTLS and SMTP_USE_TLS cannot both be true"):
        _smtp_settings(smtp_starttls=True, smtp_use_tls=True)
