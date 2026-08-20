from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    #: Minimum 12 characters (security hardening) — enforced only at registration, not
    #: at login (a login attempt must still be checked against the stored hash and
    #: rejected as INVALID_CREDENTIALS, not short-circuited by a schema-level 422 that
    #: would leak "this password is too short to even be real").
    password: str = Field(min_length=12)


class UserOut(BaseModel):
    id: str
    email: str
