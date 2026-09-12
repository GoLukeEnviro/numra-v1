from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    #: Public registration can NEVER set role/is_active/permissions — any unexpected
    #: key (e.g. "role": "ADMIN") becomes a 422 instead of being silently ignored.
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    #: Minimum 12 characters (security hardening) — enforced only at registration, not
    #: at login (a login attempt must still be checked against the stored hash and
    #: rejected as INVALID_CREDENTIALS, not short-circuited by a schema-level 422 that
    #: would leak "this password is too short to even be real").
    password: str = Field(min_length=12)


class UserOut(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool
    email_verified_at: dt.datetime | None = None


class MobileSessionOut(BaseModel):
    """One-time native credential response. Only its hash is stored server-side."""

    access_token: str
    token_type: str = "Bearer"
    expires_at: dt.datetime
    user: UserOut


class ChangePasswordRequest(BaseModel):
    """V1.5 Epic N. Same minimum-length rule as registration; the current password is
    always required (never trust a signed-in session alone to authorize a password
    change — a hijacked/left-open session should not be enough)."""

    current_password: str
    new_password: str = Field(min_length=12)


class VerifyEmailRequest(BaseModel):
    """`extra="forbid"` like `RegisterRequest` -- an unauthenticated body accepting
    unknown keys is exactly the surface that must stay closed here."""

    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1)


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1)
    #: Same minimum-length rule as registration/change-password.
    new_password: str = Field(min_length=12)


class SessionOut(BaseModel):
    """One active session (V1.5 Epic N). No IP address or device identifier is
    stored or returned — sessions carry only a token hash, timestamps, and the
    owning user (see models.tables.Session)."""

    id: str
    created_at: dt.datetime
    expires_at: dt.datetime
    is_current: bool


class SystemInfoOut(BaseModel):
    """Sanitized system info for the signed-in user's Settings page (V1.5 Epic N).
    Deliberately excludes every secret (session_secret, pdf_internal_token,
    ollama_api_key, database_url) -- only operational facts a user could otherwise
    infer from how the app behaves."""

    environment: str
    app_timezone: str
    session_ttl_hours: int
    self_signup_enabled: bool
    llm_provider: str
    pdf_export_enabled: bool
