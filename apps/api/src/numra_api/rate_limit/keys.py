"""Pseudonymizes the raw identity (client IP, user id) a rate-limit key is derived
from. Rate-limit keys are never stored/logged as plaintext IP addresses or user ids --
an HMAC (keyed with the app's own secret, so it isn't reversible without that secret)
stands in for them, matching the same principle applied to session tokens elsewhere in
this codebase.
"""

from __future__ import annotations

import hashlib
import hmac

__all__ = ["pseudonymous_key"]


def pseudonymous_key(raw: str, *, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest[:32]
