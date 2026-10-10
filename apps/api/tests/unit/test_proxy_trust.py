from __future__ import annotations

import pytest
from pydantic import ValidationError

from numra_api.config import Settings
from numra_api.proxy_trust import ProxyTrust, normalize_ip, parse_networks

pytestmark = pytest.mark.unit

_DB_URL = "postgresql+asyncpg://numra:numra_dev_password@127.0.0.1:5432/numra_test"
CURRENT = "c" * 40
PREVIOUS = "p" * 40
TRUSTED_PEER = "172.18.0.5"


def _trust(secrets: list[str]) -> ProxyTrust:
    return ProxyTrust(secrets=secrets, trusted_networks=parse_networks(["172.16.0.0/12"]))


def test_valid_secret_and_trusted_peer_accept_forwarded_ip() -> None:
    ctx = _trust([CURRENT]).evaluate(
        peer=TRUSTED_PEER, presented_secret=CURRENT, forwarded_for="203.0.113.9"
    )
    assert (ctx.client_ip, ctx.proxy_authenticated, ctx.forwarded_ip_accepted) == (
        "203.0.113.9",
        True,
        True,
    )


def test_valid_secret_untrusted_peer_falls_back_to_peer() -> None:
    ctx = _trust([CURRENT]).evaluate(
        peer="198.51.100.7", presented_secret=CURRENT, forwarded_for="203.0.113.9"
    )
    assert ctx.client_ip == "198.51.100.7"
    assert ctx.proxy_authenticated is True
    assert ctx.forwarded_ip_accepted is False


@pytest.mark.parametrize("presented", [None, "", "wrong" * 10])
def test_missing_or_wrong_secret_ignores_forwarded_ip(presented: str | None) -> None:
    ctx = _trust([CURRENT]).evaluate(
        peer=TRUSTED_PEER, presented_secret=presented, forwarded_for="203.0.113.9"
    )
    assert ctx.client_ip == TRUSTED_PEER
    assert ctx.proxy_authenticated is False


def test_empty_trusted_list_never_accepts_forwarded_ip() -> None:
    trust = ProxyTrust(secrets=[CURRENT], trusted_networks=())
    ctx = trust.evaluate(peer=TRUSTED_PEER, presented_secret=CURRENT, forwarded_for="203.0.113.9")
    assert ctx.client_ip == TRUSTED_PEER


def test_no_configured_secret_never_authenticates() -> None:
    ctx = _trust([]).evaluate(peer=TRUSTED_PEER, presented_secret="x" * 40, forwarded_for="1.2.3.4")
    assert ctx.proxy_authenticated is False
    assert ctx.client_ip == TRUSTED_PEER


@pytest.mark.parametrize(
    ("secrets", "presented", "valid"),
    [
        ([CURRENT, PREVIOUS], CURRENT, True),
        ([CURRENT, PREVIOUS], PREVIOUS, True),
        ([CURRENT], PREVIOUS, False),  # nach Abschluss der Rotation: altes Secret tot
        ([PREVIOUS], PREVIOUS, True),  # Rückroll: nur das alte Secret konfiguriert
        ([CURRENT, PREVIOUS], "z" * 40, False),
    ],
)
def test_rotation_matrix(secrets: list[str], presented: str, valid: bool) -> None:
    ctx = _trust(secrets).evaluate(
        peer=TRUSTED_PEER, presented_secret=presented, forwarded_for=None
    )
    assert ctx.proxy_authenticated is valid


def test_multiple_forwarded_entries_use_rightmost_and_garbage_is_rejected() -> None:
    trust = _trust([CURRENT])
    multi = trust.evaluate(
        peer=TRUSTED_PEER, presented_secret=CURRENT, forwarded_for="6.6.6.6, 203.0.113.9"
    )
    assert multi.client_ip == "203.0.113.9"
    garbage = trust.evaluate(peer=TRUSTED_PEER, presented_secret=CURRENT, forwarded_for="not-an-ip")
    assert garbage.client_ip == TRUSTED_PEER
    assert garbage.forwarded_ip_accepted is False


def test_ipv4_mapped_ipv6_is_normalised() -> None:
    assert normalize_ip("::ffff:203.0.113.9") == "203.0.113.9"
    assert normalize_ip("garbage") is None


def test_settings_reject_short_secret_without_leaking_it() -> None:
    with pytest.raises(ValidationError) as excinfo:
        Settings(database_url=_DB_URL, environment="test", internal_proxy_shared_secret="short")
    assert "short'" not in str(excinfo.value)
    assert "mindestens 32" in str(excinfo.value)


def test_settings_previous_requires_current_and_must_differ() -> None:
    with pytest.raises(ValidationError, match="PREVIOUS erfordert"):
        Settings(
            database_url=_DB_URL, environment="test", internal_proxy_shared_secret_previous=PREVIOUS
        )
    with pytest.raises(ValidationError, match="darf nicht dem aktuellen"):
        Settings(
            database_url=_DB_URL,
            environment="test",
            internal_proxy_shared_secret=CURRENT,
            internal_proxy_shared_secret_previous=CURRENT,
        )


def test_settings_enforced_requires_secret() -> None:
    with pytest.raises(ValidationError, match="PROXY_SECRET_ENFORCED=true erfordert"):
        Settings(database_url=_DB_URL, environment="test", proxy_secret_enforced=True)


def test_settings_cidrs_from_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "172.16.0.0/12, 10.0.0.0/8")
    settings = Settings(database_url=_DB_URL, environment="test")
    assert settings.trusted_proxy_cidrs == ["172.16.0.0/12", "10.0.0.0/8"]
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "not-a-cidr")
    with pytest.raises(ValidationError, match="gültige CIDR"):
        Settings(database_url=_DB_URL, environment="test")


def test_settings_repr_hides_secrets() -> None:
    settings = Settings(
        database_url=_DB_URL,
        environment="test",
        internal_proxy_shared_secret=CURRENT,
        internal_proxy_shared_secret_previous=PREVIOUS,
    )
    assert CURRENT not in repr(settings)
    assert PREVIOUS not in repr(settings)
    assert settings.proxy_secret_values == [CURRENT, PREVIOUS]
