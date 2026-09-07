from __future__ import annotations

import pytest

from numra_api.auth.tokens import generate_token, hash_token

pytestmark = pytest.mark.unit


def test_generate_token_is_random_and_url_safe() -> None:
    first = generate_token()
    second = generate_token()
    assert first != second
    assert len(first) > 32
    # URL-safe base64 alphabet only -- these tokens go straight into a query string
    # (see services/auth_recovery_service.py's verify-email/reset-password links).
    assert all(c.isalnum() or c in "-_" for c in first)


def test_hash_token_is_deterministic_sha256_hex() -> None:
    token = "a-fixed-example-token"
    assert hash_token(token) == hash_token(token)
    digest = hash_token(token)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_hash_token_differs_for_different_tokens() -> None:
    assert hash_token(generate_token()) != hash_token(generate_token())


def test_session_token_wrappers_delegate_to_tokens_module() -> None:
    """auth/sessions.py's generate_session_token/hash_session_token are thin wrappers
    around auth/tokens.py (see the DRY refactor) -- must stay behaviorally identical."""
    from numra_api.auth.sessions import generate_session_token, hash_session_token

    token = generate_session_token()
    assert hash_session_token(token) == hash_token(token)
