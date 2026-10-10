from __future__ import annotations

import logging

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from numra_api.proxy_trust import (
    FORWARDED_FOR_HEADER,
    FORWARDING_CLAIM_HEADERS,
    PROXY_AUTH_HEADER,
    ProxyTrust,
)

_logger = logging.getLogger("numra_api.proxy_trust")


class ProxyTrustMiddleware:
    """Ermittelt je Request die vertrauenswürdige Client-IP (`scope["state"]["client_ip"]`)
    und ob der Aufrufer sich als interner Proxy ausgewiesen hat. Pure ASGI (siehe
    Hinweis in security.py).

    Übergangsmodus (`enforced=False`): ungültiger/fehlender Header → Peer-Adresse, nur
    Warn-Log mit Grund (nie dem Header-Wert). `enforced=True`: behauptete Proxy-Identität
    ohne gültiges Secret sowie Cookie-Sessions ohne gültiges Secret → 403. Mobile
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
            forwarded_for=headers.get(FORWARDED_FOR_HEADER),
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
        if any(name in headers for name in FORWARDING_CLAIM_HEADERS):
            return True
        cookie_header = headers.get("cookie", "")
        return any(
            part.strip().startswith(f"{self.session_cookie_name}=")
            for part in cookie_header.split(";")
        )
