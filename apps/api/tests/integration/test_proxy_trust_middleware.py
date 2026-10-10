"""ProxyTrustMiddleware end to end (ASGI, echte App-Instanz, Test-DB).

Der TCP-Peer wird über `ASGITransport(client=...)` gesetzt. Eine reine Test-Route
(`/__test/ip`) gibt die ermittelte Client-IP zurück.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import pytest
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from numra_api.app import create_app
from numra_api.auth.passwords import hash_password
from numra_api.config import Settings
from numra_api.db import build_sessionmaker
from numra_api.deps import client_ip_of
from numra_api.rate_limit import pseudonymous_key
from numra_api.rate_limit.limiter import InMemoryRateLimiter, RateLimitResult
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration

CURRENT = "current-secret-" + "c" * 30
PREVIOUS = "previous-secret-" + "p" * 30
TRUSTED_PEER = "172.18.0.5"
CIDRS = ["172.16.0.0/12"]
PASSWORD = "correct horse battery staple"
HEADER = "X-Numra-Proxy-Auth"


@pytest.fixture
def make_client(settings: Settings, db_engine) -> Callable[..., object]:
    @asynccontextmanager
    async def _make(
        *, peer: str = TRUSTED_PEER, recorder: list[str] | None = None, **overrides: object
    ) -> AsyncIterator[AsyncClient]:
        config = {"trusted_proxy_cidrs": CIDRS, "allow_self_signup": True, **overrides}
        for name in ("internal_proxy_shared_secret", "internal_proxy_shared_secret_previous"):
            if isinstance(config.get(name), str):
                config[name] = SecretStr(config[name])  # model_copy validiert nicht
        app = create_app(settings=settings.model_copy(update=config))
        app.state.engine = db_engine
        app.state.sessionmaker = build_sessionmaker(db_engine)

        @app.get("/__test/ip")
        async def _ip(request: Request) -> dict[str, str]:
            return {"ip": client_ip_of(request)}

        if recorder is not None:
            inner = InMemoryRateLimiter()

            class Recording:
                async def check(
                    self, *, key: str, limit: int, window_seconds: int
                ) -> RateLimitResult:
                    recorder.append(key)
                    return await inner.check(key=key, limit=limit, window_seconds=window_seconds)

            app.state.rate_limiter = Recording()
        transport = ASGITransport(app=app, client=(peer, 50000))
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac

    return _make


async def _seed_user(client: AsyncClient, email: str) -> None:
    sessionmaker = client._transport.app.state.sessionmaker  # type: ignore[attr-defined]
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password(PASSWORD))
        await db.commit()


async def test_forged_forwarded_headers_from_outside_are_ignored(make_client) -> None:
    async with make_client(internal_proxy_shared_secret=CURRENT, peer="198.51.100.7") as client:
        response = await client.get(
            "/__test/ip",
            headers={"X-Forwarded-For": "1.2.3.4", "X-Real-IP": "5.6.7.8", "X-User-Id": "x"},
        )
    assert response.json() == {"ip": "198.51.100.7"}


async def test_no_secret_configured_behaves_like_before(make_client) -> None:
    async with make_client() as client:
        response = await client.get("/__test/ip", headers={"X-Forwarded-For": "1.2.3.4"})
    assert response.json() == {"ip": TRUSTED_PEER}


async def test_valid_secret_from_trusted_peer_uses_forwarded_ip(make_client) -> None:
    async with make_client(internal_proxy_shared_secret=CURRENT) as client:
        response = await client.get(
            "/__test/ip", headers={HEADER: CURRENT, "X-Forwarded-For": "203.0.113.9"}
        )
    assert response.json() == {"ip": "203.0.113.9"}


async def test_valid_secret_from_untrusted_peer_uses_peer(make_client) -> None:
    async with make_client(internal_proxy_shared_secret=CURRENT, peer="198.51.100.7") as client:
        response = await client.get(
            "/__test/ip", headers={HEADER: CURRENT, "X-Forwarded-For": "203.0.113.9"}
        )
    assert response.json() == {"ip": "198.51.100.7"}


async def test_wrong_secret_transitional_ignores_forwarded_ip_but_serves(make_client) -> None:
    async with make_client(internal_proxy_shared_secret=CURRENT) as client:
        response = await client.get(
            "/__test/ip", headers={HEADER: "w" * 40, "X-Forwarded-For": "203.0.113.9"}
        )
    assert response.status_code == 200
    assert response.json() == {"ip": TRUSTED_PEER}


async def test_enforced_rejects_wrong_secret_but_ignores_forwarded_headers_without_one(
    make_client,
) -> None:
    async with make_client(internal_proxy_shared_secret=CURRENT, proxy_secret_enforced=True) as c:
        forwarded_only = await c.get(
            "/__test/ip",
            headers={
                "X-Forwarded-For": "203.0.113.9",
                "X-Real-IP": "1.1.1.1",
                "Forwarded": "for=2.2.2.2",
            },
        )
        wrong = await c.get("/__test/ip", headers={HEADER: "w" * 40})
        good = await c.get(
            "/__test/ip", headers={HEADER: CURRENT, "X-Forwarded-For": "203.0.113.9"}
        )
    # Ingress (Cloudflare/tailscale-serve) haengt XFF an: ignoriert, nicht abgelehnt.
    assert forwarded_only.status_code == 200
    assert forwarded_only.json() == {"ip": TRUSTED_PEER}
    assert wrong.status_code == 403
    assert wrong.json()["code"] == "PROXY_AUTH_FAILED"
    assert good.json() == {"ip": "203.0.113.9"}


@pytest.mark.parametrize(
    "cookie_headers",
    [
        ["numra_session=abc"],
        ["numra_session =abc"],
        ["numra_session	=abc"],
        ["theme=dark; numra_session=abc"],
        ["theme=dark;numra_session=abc; other=1"],
        ["  numra_session=abc"],
        ["a=1", "numra_session=abc"],
    ],
)
async def test_enforced_rejects_session_cookie_in_every_parseable_form(
    make_client, cookie_headers: list[str]
) -> None:
    async with make_client(internal_proxy_shared_secret=CURRENT, proxy_secret_enforced=True) as c:
        response = await c.get("/v1/auth/me", headers=[("Cookie", v) for v in cookie_headers])
    assert response.status_code == 403
    assert response.json()["code"] == "PROXY_AUTH_FAILED"


@pytest.mark.parametrize(
    "cookie", ["xnumra_session=abc", "numra_session_x=abc", "theme=numra_session=abc"]
)
async def test_enforced_does_not_treat_lookalike_cookies_as_session(
    make_client, cookie: str
) -> None:
    async with make_client(internal_proxy_shared_secret=CURRENT, proxy_secret_enforced=True) as c:
        response = await c.get("/__test/ip", headers={"Cookie": cookie})
    assert response.status_code == 200


async def test_enforced_accepts_session_cookie_with_valid_secret(make_client) -> None:
    async with make_client(internal_proxy_shared_secret=CURRENT, proxy_secret_enforced=True) as c:
        response = await c.get(
            "/__test/ip", headers={"Cookie": "numra_session =abc", HEADER: CURRENT}
        )
    assert response.status_code == 200


async def test_rotation_current_previous_none_and_rollback(make_client) -> None:
    async def status(client: AsyncClient, secret: str) -> int:
        return (await client.get("/__test/ip", headers={HEADER: secret})).status_code

    both = {
        "internal_proxy_shared_secret": CURRENT,
        "internal_proxy_shared_secret_previous": PREVIOUS,
    }
    async with make_client(proxy_secret_enforced=True, **both) as client:
        assert await status(client, CURRENT) == 200
        assert await status(client, PREVIOUS) == 200
    # Rotation abgeschlossen: PREVIOUS entfernt -> altes Secret tot.
    async with make_client(proxy_secret_enforced=True, internal_proxy_shared_secret=CURRENT) as c:
        assert await status(c, CURRENT) == 200
        assert await status(c, PREVIOUS) == 403
    # Rückroll: Rollen vertauscht, das alte Secret ist wieder aktuell, das neue previous.
    async with make_client(
        proxy_secret_enforced=True,
        internal_proxy_shared_secret=PREVIOUS,
        internal_proxy_shared_secret_previous=CURRENT,
    ) as client:
        assert await status(client, PREVIOUS) == 200
        assert await status(client, CURRENT) == 200


async def test_health_and_mobile_paths_work_without_secret_when_enforced(make_client) -> None:
    async with make_client(internal_proxy_shared_secret=CURRENT, proxy_secret_enforced=True) as c:
        await _seed_user(c, "mobile-proxy@example.com")
        # Cloudflare/tailscale-serve haengen X-Forwarded-For an: darf nicht zu 403 fuehren.
        via_ingress = {"X-Forwarded-For": "198.51.100.20", "X-Real-IP": "198.51.100.20"}
        live = await c.get("/v1/health/live", headers=via_ingress)
        ready = await c.get("/v1/health/ready", headers=via_ingress)
        login = await c.post(
            "/v1/auth/mobile/login",
            json={"email": "mobile-proxy@example.com", "password": PASSWORD},
            headers=via_ingress,
        )
        token = login.json()["access_token"]
        me = await c.get(
            "/v1/auth/mobile/me", headers={"Authorization": f"Bearer {token}", **via_ingress}
        )
    assert ready.status_code in (200, 503)
    assert live.status_code == 200
    assert login.status_code == 200
    assert me.status_code == 200


async def test_origin_and_csrf_protection_unchanged_with_valid_secret(make_client) -> None:
    async with make_client(internal_proxy_shared_secret=CURRENT, proxy_secret_enforced=True) as c:
        await _seed_user(c, "csrf-proxy@example.com")
        proxy = {HEADER: CURRENT}
        login = await c.post(
            "/v1/auth/login",
            json={"email": "csrf-proxy@example.com", "password": PASSWORD},
            headers=proxy,
        )
        assert login.status_code == 200
        me = await c.get("/v1/auth/me", headers=proxy)
        assert me.status_code == 200
        no_csrf = await c.post("/v1/auth/logout", headers=proxy)
        bad_origin = await c.post(
            "/v1/auth/logout",
            headers={
                **proxy,
                "Origin": "https://evil.example",
                "x-csrf-token": c.cookies["numra_csrf"],
            },
        )
    assert no_csrf.status_code == 403
    assert no_csrf.json()["code"] != "PROXY_AUTH_FAILED"
    assert bad_origin.status_code == 403
    assert bad_origin.json()["code"] == "ORIGIN_NOT_ALLOWED"


async def test_user_identity_is_never_taken_from_headers(make_client) -> None:
    keys: list[str] = []
    async with make_client(recorder=keys, internal_proxy_shared_secret=CURRENT) as c:
        await _seed_user(c, "ident-proxy@example.com")
        login = await c.post(
            "/v1/auth/login", json={"email": "ident-proxy@example.com", "password": PASSWORD}
        )
        assert login.status_code == 200
        user_id = (await c.get("/v1/auth/me")).json()["id"]
        keys.clear()
        await c.post(
            "/v1/auth/request-email-verification",
            headers={
                "x-csrf-token": c.cookies["numra_csrf"],
                "X-User-Id": "00000000-0000-0000-0000-000000000000",
                HEADER: CURRENT,
            },
        )
    secret = "dev-only-insecure-secret-change-me"
    expected = f"auth:request_email_verification:{pseudonymous_key(user_id, secret=secret)}"
    assert expected in keys
    forged = pseudonymous_key("00000000-0000-0000-0000-000000000000", secret=secret)
    assert all(forged not in key for key in keys)


async def test_secret_never_appears_in_logs_or_responses(make_client, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    async with make_client(
        internal_proxy_shared_secret=CURRENT,
        internal_proxy_shared_secret_previous=PREVIOUS,
        proxy_secret_enforced=True,
    ) as c:
        responses = [
            await c.get("/__test/ip", headers={HEADER: CURRENT, "X-Forwarded-For": "203.0.113.9"}),
            await c.get("/__test/ip", headers={HEADER: PREVIOUS}),
            await c.get("/__test/ip", headers={HEADER: "wrong-" + "w" * 40}),
            await c.get(
                "/__test/ip", headers={HEADER: "wrong-" + "w" * 40, "X-Forwarded-For": "x"}
            ),
            await c.get("/v1/health/live"),
        ]
    haystack = caplog.text + "".join(r.text + str(r.headers) for r in responses)
    for secret in (CURRENT, PREVIOUS, "wrong-" + "w" * 40):
        assert secret not in haystack
    assert "secret_mismatch" in caplog.text
