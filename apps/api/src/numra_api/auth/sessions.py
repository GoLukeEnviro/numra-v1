from __future__ import annotations

from numra_api.auth.tokens import generate_token, hash_token


def generate_session_token() -> str:
    """Cryptographically random session token. Only its hash is ever persisted."""
    return generate_token()


def hash_session_token(token: str) -> str:
    return hash_token(token)
