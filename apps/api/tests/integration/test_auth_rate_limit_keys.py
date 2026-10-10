"""Rate-limit key kinds on the auth endpoints: trusted client IP (pre-login), user id
(post-login), and target address/account -- configurable, enumeration-free, fail-closed.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from redis.asyncio import from_url

from numra_api.app import create_app
from numra_api.auth.passwords import hash_password
from numra_api.config import Settings
from numra_api.db import build_sessionmaker
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration

SECRET = "rate-limit-test-secret-" + "x" * 20
PEER = "172.18.0.5"
PASSWORD = "correct horse battery staple"
PROXY = {"X-Numra-Proxy-Auth": SECRET}
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6379/14")


def _via(ip: str) -> dict[str, str]:
    return {**PROXY, "X-Forwarded-For": ip}


class RecordingSender:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, *, to: str, subject: str, body: str, html_body: str | None = None) -> None:
        self.sent.append({"to": to, "subject": subject})


@pytest.fixture
def make_client(settings: Settings, db_engine) -> Callable[..., object]:
    @asynccontextmanager
    async def _make(
        *, overrides: dict[str, str] | None = None, **extra: object
    ) -> AsyncIterator[AsyncClient]:
        config: dict[str, object] = {
            "allow_self_signup": True,
            "internal_proxy_shared_secret": SecretStr(SECRET),
            "trusted_proxy_cidrs": ["172.16.0.0/12"],
            "rate_limit_overrides": overrides or {},
            **extra,
        }
        app = create_app(settings=settings.model_copy(update=config))
        app.state.engine = db_engine
        app.state.sessionmaker = build_sessionmaker(db_engine)
        app.state.email_sender = RecordingSender()
        transport = ASGITransport(app=app, client=(PEER, 50000))
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac

    return _make


async def _seed(client: AsyncClient, email: str) -> None:
    async with client._transport.app.state.sessionmaker() as db:  # type: ignore[attr-defined]
        await create_user(db, email=email, password_hash=hash_password(PASSWORD))
        await db.commit()


async def _login(client: AsyncClient, email: str, headers: dict[str, str]) -> int:
    body = {"email": email, "password": "wrong-password-123"}
    return (await client.post("/v1/auth/login", json=body, headers=headers)).status_code


async def test_ip_buckets_follow_the_trusted_client_ip_not_the_proxy_peer(make_client) -> None:
    async with make_client(overrides={"auth:login": "2/60"}) as c:
        # Gleicher Proxy-Peer, zwei echte Clients: jeder hat seinen eigenen Zähler.
        assert [await _login(c, "a@example.com", _via("203.0.113.1")) for _ in range(3)] == [
            401,
            401,
            429,
        ]
        assert await _login(c, "a@example.com", _via("203.0.113.2")) == 401


async def test_forged_forwarded_for_without_secret_cannot_escape_the_ip_bucket(
    make_client,
) -> None:
    async with make_client(overrides={"auth:login": "2/60"}) as c:
        statuses = [
            await _login(c, "b@example.com", {"X-Forwarded-For": f"203.0.113.{n}"})
            for n in range(1, 5)
        ]
    assert statuses == [401, 401, 429, 429]


async def test_login_target_limit_is_per_address_across_ips_and_enumeration_free(
    make_client,
) -> None:
    async with make_client(overrides={"auth:login:target": "3/60"}) as c:
        await _seed(c, "known@example.com")
        known = [
            await c.post(
                "/v1/auth/login",
                json={"email": "known@example.com", "password": "wrong-password-123"},
                headers=_via(f"203.0.113.{n}"),
            )
            for n in range(1, 5)
        ]
        unknown = [
            await c.post(
                "/v1/auth/login",
                json={"email": "unknown@example.com", "password": "wrong-password-123"},
                headers=_via(f"203.0.113.{n}"),
            )
            for n in range(1, 5)
        ]
        other = await _login(c, "third@example.com", _via("203.0.113.1"))
    # Bekannt und unbekannt verhalten sich Schritt für Schritt identisch ...
    assert (
        [r.status_code for r in known] == [r.status_code for r in unknown] == [401, 401, 401, 429]
    )
    # ... und der 429-Body enthält weder Adresse noch Kontohinweis.
    assert known[3].json() == unknown[3].json()
    assert "example.com" not in known[3].text
    assert other == 401


async def test_email_normalisation_shares_one_target_bucket(make_client) -> None:
    async with make_client(overrides={"auth:login:target": "2/60"}) as c:
        results = [
            await _login(c, address, _via(f"203.0.113.{n}"))
            for n, address in enumerate(["Foo@Example.com", " foo@example.com", "FOO@EXAMPLE.COM"])
        ]
    assert results == [401, 401, 429]


async def test_mobile_login_shares_the_login_target_bucket(make_client) -> None:
    async with make_client(overrides={"auth:login:target": "2/60"}) as c:
        await _seed(c, "mob@example.com")
        body = {"email": "mob@example.com", "password": "wrong-password-123"}
        first = await c.post("/v1/auth/mobile/login", json=body, headers=_via("203.0.113.1"))
        second = await c.post("/v1/auth/login", json=body, headers=_via("203.0.113.2"))
        third = await c.post("/v1/auth/mobile/login", json=body, headers=_via("203.0.113.3"))
    assert (first.status_code, second.status_code, third.status_code) == (401, 401, 429)


async def test_register_target_and_ip_limits(make_client) -> None:
    async with make_client(
        overrides={"auth:register:target": "2/3600", "auth:register": "3/3600"}
    ) as c:

        def payload(email: str) -> dict:
            return {"email": email, "password": "password12345", "age_confirmed": True}

        same_target = [
            (await c.post("/v1/auth/register", json=payload("dup@example.com"), headers=_via(ip)))
            for ip in ("203.0.113.1", "203.0.113.2", "203.0.113.3")
        ]
        by_ip = [
            await c.post(
                "/v1/auth/register", json=payload(f"n{n}@example.com"), headers=_via("203.0.113.9")
            )
            for n in range(4)
        ]
    assert [r.status_code for r in same_target] == [201, 409, 429]
    assert [r.status_code for r in by_ip] == [201, 201, 201, 429]


async def test_forgot_password_limits_are_uniform_for_known_and_unknown_addresses(
    make_client,
) -> None:
    async with make_client(overrides={"auth:forgot_password:target": "2/3600"}) as c:
        await _seed(c, "reset-known@example.com")
        sender = c._transport.app.state.email_sender  # type: ignore[attr-defined]

        async def hits(email: str) -> list[int]:
            return [
                (
                    await c.post(
                        "/v1/auth/forgot-password",
                        json={"email": email},
                        headers=_via(f"203.0.113.{n}"),
                    )
                ).status_code
                for n in range(1, 4)
            ]

        known = await hits("reset-known@example.com")
        unknown = await hits("reset-unknown@example.com")
    assert known == unknown == [202, 202, 429]
    # Das gesperrte dritte Mal hat keine weitere Mail ausgelöst.
    assert len(sender.sent) == 2


async def test_verification_send_has_user_and_ip_limits(make_client) -> None:
    async with make_client(
        overrides={
            "auth:request_email_verification": "2/3600",
            "auth:request_email_verification:ip": "3/3600",
        }
    ) as c:
        await _seed(c, "ver@example.com")
        await _seed(c, "ver2@example.com")
        login = await c.post(
            "/v1/auth/login",
            json={"email": "ver@example.com", "password": PASSWORD},
            headers=_via("203.0.113.1"),
        )
        assert login.status_code == 200
        csrf = {"x-csrf-token": c.cookies["numra_csrf"]}

        # Nutzer-Zähler greift unabhängig von der IP: dieselbe Session, wechselnde Quellen.
        codes = [
            (
                await c.post(
                    "/v1/auth/request-email-verification",
                    headers={**csrf, **_via(f"203.0.113.{n}")},
                )
            ).status_code
            for n in range(1, 4)
        ]
    assert codes == [204, 204, 429]


async def test_user_bucket_ignores_spoofed_user_header(make_client) -> None:
    async with make_client(overrides={"auth:request_email_verification": "1/3600"}) as c:
        await _seed(c, "spoof@example.com")
        await c.post(
            "/v1/auth/login",
            json={"email": "spoof@example.com", "password": PASSWORD},
            headers=PROXY,
        )
        csrf = {"x-csrf-token": c.cookies["numra_csrf"]}
        first = await c.post("/v1/auth/request-email-verification", headers={**csrf, **PROXY})
        spoofed = await c.post(
            "/v1/auth/request-email-verification",
            headers={**csrf, **PROXY, "X-User-Id": "11111111-1111-1111-1111-111111111111"},
        )
    assert (first.status_code, spoofed.status_code) == (204, 429)


async def test_limiter_backend_outage_fails_closed_without_leaking_details(make_client) -> None:
    class Broken:
        async def check(self, **_: object) -> object:
            raise ConnectionError("redis://:s3cr3t-pass@redis:6379/0 refused")

    async with make_client() as c:
        c._transport.app.state.rate_limiter = Broken()  # type: ignore[attr-defined]
        response = await c.post(
            "/v1/auth/login", json={"email": "x@example.com", "password": "wrong-password-123"}
        )
    assert response.status_code == 503
    assert response.json()["code"] == "RATE_LIMIT_UNAVAILABLE"
    assert "s3cr3t" not in response.text and "redis" not in response.text


async def test_redis_backend_enforces_target_limit_across_instances(make_client) -> None:
    client = from_url(TEST_REDIS_URL)
    await client.flushdb()
    try:
        extra = {"rate_limit_backend": "redis", "redis_url": TEST_REDIS_URL}
        overrides = {"auth:login:target": "2/60"}
        async with (
            make_client(overrides=overrides, **extra) as first,
            make_client(overrides=overrides, **extra) as second,
        ):
            a = await _login(first, "shared@example.com", _via("203.0.113.1"))
            b = await _login(second, "shared@example.com", _via("203.0.113.2"))
            c = await _login(first, "shared@example.com", _via("203.0.113.3"))
        assert (a, b, c) == (401, 401, 429)
    finally:
        await client.flushdb()
        await client.aclose()


async def test_unknown_override_policy_and_bad_spec_are_rejected_at_startup() -> None:
    from pydantic import ValidationError

    db = "postgresql+asyncpg://numra:numra_dev_password@127.0.0.1:5432/numra_test"
    with pytest.raises(ValidationError, match="unbekannte Policy"):
        Settings(database_url=db, environment="test", rate_limit_overrides={"nope": "1/1"})
    with pytest.raises(ValidationError, match="erwartet"):
        Settings(database_url=db, environment="test", rate_limit_overrides={"auth:login": "10"})
    with pytest.raises(ValidationError, match=">= 1"):
        Settings(database_url=db, environment="test", rate_limit_overrides={"auth:login": "0/60"})
