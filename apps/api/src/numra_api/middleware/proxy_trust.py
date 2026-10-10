from __future__ import annotations

import logging

from starlette.datastructures import Headers
from starlette.requests import cookie_parser
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from numra_api.proxy_trust import (
    FORWARDED_FOR_HEADER,
    PROXY_AUTH_HEADER,
    ProxyTrust,
)

_logger = logging.getLogger("numra_api.proxy_trust")


class ProxyTrustMiddleware:
    """Ermittelt je Request die vertrauenswürdige Client-IP (`scope["state"]["client_ip"]`)
    und ob der Aufrufer sich als interner Proxy ausgewiesen hat. Pure ASGI (siehe
    Hinweis in security.py).

    Übergangsmodus (`enforced=False`): ungültiger/fehlender Header → Peer-Adresse, nur
    Warn-Log mit Grund (nie dem Header-Wert). `enforced=True`: Cookie-Sessions und
    Requests mit `X-Numra-Proxy-Auth` ohne gültiges Secret → 403. Mobile
    (Bearer) und `/v1/health/*` tragen weder Cookie noch Proxy-Header und bleiben frei."""

    def __init__(
        self, app: ASGIApp, *, trust: ProxyTrust, enforced: bool, session_cookie_name: str
    ) -> None:
        self.app = app
        self.trust = trust
        self.enforced = enforced
        self.session_cookie_name = session_cookie_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        client = scope.get("client")
        peer = client[0] if client else None
        context = self.trust.evaluate(
            peer=peer,
            presented_secret=headers.get(PROXY_AUTH_HEADER),
            forwarded_for=",".join(headers.getlist(FORWARDED_FOR_HEADER)) or None,
        )

        if context.auth_state == "invalid":
            _logger.warning("proxy auth rejected: secret_mismatch")
        elif (
            context.proxy_authenticated
            and FORWARDED_FOR_HEADER in headers
            and not context.forwarded_ip_accepted
        ):
            _logger.warning("forwarded client ip not accepted: peer_not_trusted_or_ip_invalid")

        if self.enforced and not context.proxy_authenticated and self._needs_proxy(headers):
            response = JSONResponse(
                status_code=403,
                content={"code": "PROXY_AUTH_FAILED", "message": "internal access not permitted"},
            )
            await response(scope, receive, send)
            return

        state = scope.setdefault("state", {})
        state["client_ip"] = context.client_ip
        state["proxy_authenticated"] = context.proxy_authenticated
        await self.app(scope, receive, send)

    def _needs_proxy(self, headers: Headers) -> bool:
        """Erzwingung nur für (a) Cookie-Sessions und (b) Requests, die sich per
        `X-Numra-Proxy-Auth` als Proxy ausgeben. Forwarded-Header ohne gültiges Secret
        (Mobile/Health hinter Cloudflare/tailscale-serve tragen sie) werden ignoriert,
        nicht abgelehnt. Cookies werden exakt wie von Starlette geparst, damit
        `numra_session =tok` oder Tab-Varianten nicht an der Prüfung vorbeikommen."""
        if PROXY_AUTH_HEADER in headers:
            return True
        return any(
            self.session_cookie_name in cookie_parser(value) for value in headers.getlist("cookie")
        )
