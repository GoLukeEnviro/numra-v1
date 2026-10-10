from __future__ import annotations

from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    return _hasher.hash(plain_password)


def verify_password(password_hash: str, plain_password: str) -> bool:
    try:
        return _hasher.verify(password_hash, plain_password)
    except VerifyMismatchError:
        return False


@lru_cache(maxsize=1)
def dummy_password_hash() -> str:
    """Hash with the production Argon2 parameters for a password nobody knows. Verified
    when the login address is unknown so that unknown and known addresses cost the same
    Argon2 work (no timing oracle for account existence)."""
    return _hasher.hash("numra-timing-equaliser-not-a-credential")
