"""Vertrauensgrenze zwischen Web-BFF und API.

Die API übernimmt eine vom Proxy gemeldete Client-IP nur, wenn der Proxy sich mit dem
gemeinsamen Secret (`X-Numra-Proxy-Auth`) ausweist UND der TCP-Peer in der Trusted-
Proxy-Liste steht. Nutzer-IDs werden nie aus Headern übernommen. Das Secret erscheint
weder in Logs noch in Fehlertexten; verglichen wird in konstanter Zeit.
"""

from __future__ import annotations

import hmac
import ipaddress
from dataclasses import dataclass
from typing import Literal

PROXY_AUTH_HEADER = "x-numra-proxy-auth"
FORWARDED_FOR_HEADER = "x-forwarded-for"
#: Header, mit denen ein Aufrufer eine Proxy-Identität behauptet. Ohne gültiges Secret
#: werden sie ignoriert (und unter `proxy_secret_enforced` abgelehnt).
FORWARDING_CLAIM_HEADERS = (
    FORWARDED_FOR_HEADER,
    "x-real-ip",
    "forwarded",
    PROXY_AUTH_HEADER,
)

IpAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
IpNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network

ProxyAuthState = Literal["valid", "invalid", "absent"]


@dataclass(frozen=True)
class ProxyContext:
    client_ip: str
    proxy_authenticated: bool
    auth_state: ProxyAuthState
    forwarded_ip_accepted: bool


def normalize_ip(value: str) -> str | None:
    try:
        parsed = ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped is not None:
        parsed = parsed.ipv4_mapped
    return str(parsed)


def parse_networks(cidrs: list[str]) -> tuple[IpNetwork, ...]:
    return tuple(ipaddress.ip_network(cidr.strip(), strict=False) for cidr in cidrs if cidr.strip())


class ProxyTrust:
    def __init__(
        self,
        *,
        secrets: list[str],
        trusted_networks: tuple[IpNetwork, ...],
    ) -> None:
        self._secrets = [s.encode("utf-8") for s in secrets if s]
        self._networks = trusted_networks

    def _auth_state(self, presented: str | None) -> ProxyAuthState:
        if presented is None:
            return "absent"
        candidate = presented.encode("utf-8")
        # Alle Kandidaten vergleichen (kein Short-Circuit), damit current/previous
        # zeitlich nicht unterscheidbar sind.
        matches = [hmac.compare_digest(candidate, secret) for secret in self._secrets]
        return "valid" if any(matches) else "invalid"

    def _peer_trusted(self, peer: str) -> bool:
        normalized = normalize_ip(peer)
        if normalized is None:
            return False
        address = ipaddress.ip_address(normalized)
        return any(address in network for network in self._networks)

    def evaluate(
        self, *, peer: str | None, presented_secret: str | None, forwarded_for: str | None
    ) -> ProxyContext:
        peer_ip = normalize_ip(peer) if peer else None
        fallback = peer_ip or "unknown"
        state = self._auth_state(presented_secret)
        if state != "valid" or peer_ip is None or not self._peer_trusted(peer_ip):
            return ProxyContext(fallback, state == "valid", state, False)
        forwarded = _last_forwarded_ip(forwarded_for)
        if forwarded is None:
            return ProxyContext(fallback, True, state, False)
        return ProxyContext(forwarded, True, state, True)


def _last_forwarded_ip(header: str | None) -> str | None:
    """Der Web-Rand setzt genau einen Wert; bei mehreren zählt der rechteste (der vom
    nächsten vertrauenswürdigen Hop angehängte)."""
    if not header:
        return None
    return normalize_ip(header.split(",")[-1])
