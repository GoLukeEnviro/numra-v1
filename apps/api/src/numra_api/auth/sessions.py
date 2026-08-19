from __future__ import annotations

import hashlib
import secrets

SESSION_TOKEN_BYTES = 32


def generate_session_token() -> str:
    """Cryptographically random session token. Only its hash is ever persisted."""
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
