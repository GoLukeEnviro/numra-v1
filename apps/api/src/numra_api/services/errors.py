from __future__ import annotations


class ApplicationError(Exception):
    code: str = "APPLICATION_ERROR"
    status_code: int = 400


class FutureBirthDateNotAllowed(ApplicationError):
    code = "FUTURE_BIRTH_DATE_NOT_ALLOWED"
    status_code = 422


class NotFoundError(ApplicationError):
    code = "NOT_FOUND"
    status_code = 404


class InvalidCredentials(ApplicationError):
    code = "INVALID_CREDENTIALS"
    status_code = 401


class NotAuthenticated(ApplicationError):
    code = "NOT_AUTHENTICATED"
    status_code = 401


class SelfSignupDisabled(ApplicationError):
    code = "SELF_SIGNUP_DISABLED"
    status_code = 403


class CsrfValidationFailed(ApplicationError):
    code = "CSRF_VALIDATION_FAILED"
    status_code = 403


class ReportNotReady(ApplicationError):
    code = "REPORT_NOT_READY"
    status_code = 409


class ExportRenderFailed(ApplicationError):
    code = "EXPORT_RENDER_FAILED"
    status_code = 502
