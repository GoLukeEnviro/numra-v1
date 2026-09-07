from __future__ import annotations

import hashlib
import secrets

TOKEN_BYTES = 32


def generate_token() -> str:
    """Cryptographically random token. Only its hash is ever persisted.

    Shared by every bearer-token flow that follows this shape (sessions, email
    verification, password reset) so the generation/hashing scheme can never
    drift between them."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
