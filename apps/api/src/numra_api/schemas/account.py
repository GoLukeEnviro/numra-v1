from __future__ import annotations

from pydantic import BaseModel


class DeleteAccountRequest(BaseModel):
    """Re-authentication is required to confirm irreversible account deletion
    (master prompt §137)."""

    password: str
