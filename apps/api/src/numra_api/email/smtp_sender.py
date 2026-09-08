"""`EmailSender` implementation that actually delivers via SMTP (aiosmtplib) --
`Settings.email_backend="smtp"` (see services/email_factory.py).

Every failure mode aiosmtplib can raise is translated into one of the
`EmailDeliveryUnavailable` subclasses in services/errors.py (`SmtpConnectionError`/
`SmtpTimeoutError` retryable, `SmtpAuthenticationError`/`SmtpConfigurationError` not)
so callers -- concretely services/auth_recovery_service.py, whose forgot_password MUST
catch `EmailDeliveryUnavailable` for anti-enumeration -- never need to know aiosmtplib
exists. `Settings.smtp_password` is only ever unwrapped via `get_secret_value()` right
here, immediately before the one real network call; it is never logged or included in
any exception message.
"""

from __future__ import annotations

import logging
from email.message import EmailMessage

import aiosmtplib

from numra_api.config import Settings
from numra_api.services.errors import (
    SmtpAuthenticationError,
    SmtpConfigurationError,
    SmtpConnectionError,
    SmtpTimeoutError,
)

__all__ = ["SmtpEmailSender"]

logger = logging.getLogger(__name__)


class SmtpEmailSender:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send(self, *, to: str, subject: str, body: str, html_body: str | None = None) -> None:
        settings = self._settings
        if not settings.smtp_host or not settings.smtp_port or not settings.smtp_from_email:
            raise SmtpConfigurationError(
                "EMAIL_BACKEND=smtp requires SMTP_HOST, SMTP_PORT and SMTP_FROM_EMAIL to be set"
            )

        message = self._build_message(to=to, subject=subject, body=body, html_body=html_body)
        try:
            await aiosmtplib.send(
                message,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_username,
                password=(
                    settings.smtp_password.get_secret_value() if settings.smtp_password else None
                ),
                timeout=settings.smtp_timeout_seconds,
                use_tls=settings.smtp_use_tls,
                start_tls=settings.smtp_starttls,
            )
        except aiosmtplib.SMTPAuthenticationError as exc:
            raise SmtpAuthenticationError(
                "SMTP server rejected the configured credentials"
            ) from exc
        except aiosmtplib.SMTPTimeoutError as exc:
            raise SmtpTimeoutError("SMTP operation exceeded SMTP_TIMEOUT_SECONDS") from exc
        except (aiosmtplib.SMTPConnectError, ConnectionError) as exc:
            raise SmtpConnectionError("could not connect to the configured SMTP server") from exc
        except aiosmtplib.SMTPException as exc:
            raise SmtpConnectionError("SMTP server rejected the message") from exc

    def _build_message(
        self, *, to: str, subject: str, body: str, html_body: str | None
    ) -> EmailMessage:
        settings = self._settings
        message = EmailMessage()
        from_name = settings.smtp_from_name
        from_email = settings.smtp_from_email
        message["From"] = f"{from_name} <{from_email}>" if from_name else from_email
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        if html_body is not None:
            message.add_alternative(html_body, subtype="html")
        return message
