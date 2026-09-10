"""Regression: a write endpoint's own COMMIT must land before its 2xx response
leaves the process, so the immediately-following request sees the row it just wrote.

This reproduces the recurring CI flake in
apps/web/e2e-system/system-journey.spec.ts (PR-WEB-02/03/04): POST /v1/people 201
-> POST .../calculations 404, POST /v1/relationships 201 -> GET .../{id} 404,
delete-all 204 -> re-register 409. Root cause: numra_api.deps.get_db commits in the
exit half of a FastAPI "dependency with yield"; starlette BaseHTTPMiddleware defers
that half until after the response is already sent. Under a real socket server the
next request then runs against a fresh connection before the commit lands.

The test runs a real uvicorn server (ASGITransport would hide the bug -- it drains
the response in-process, which lets the deferred teardown finish first) and forces
the timing window wide open by slowing the commit. With pure ASGI middleware the
teardown runs before the response, so the follow-up GET is 200 even with a slow
commit; with BaseHTTPMiddleware it was a deterministic 404.
"""

from __future__ import annotations

import asyncio
import contextlib
import socket

import httpx
import pytest
import pytest_asyncio
import uvicorn
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.auth.passwords import hash_password
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration

PASSWORD = "password12345"
SLOW_COMMIT_SECONDS = 0.75


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


@pytest_asyncio.fixture
async def live_server(app) -> str:
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="on")
    server = uvicorn.Server(config)
    serve_task = asyncio.create_task(server.serve())
    try:
        for _ in range(500):
            if server.started:
                break
            await asyncio.sleep(0.02)
        assert server.started, "uvicorn did not start"
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(serve_task, timeout=10)


@pytest_asyncio.fixture
async def slow_commit(monkeypatch) -> None:
    original = AsyncSession.commit
    armed = {"on": False}

    async def _slow(self: AsyncSession, *args, **kwargs):
        if armed["on"]:
            await asyncio.sleep(SLOW_COMMIT_SECONDS)
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "commit", _slow, raising=True)
    return armed


async def test_row_is_visible_to_the_next_request_right_after_its_write(
    live_server: str, sessionmaker, slow_commit
) -> None:
    async with sessionmaker() as db:
        await create_user(db, email="ordering@example.com", password_hash=hash_password(PASSWORD))
        await db.commit()

    async with httpx.AsyncClient(base_url=live_server) as client:
        login = await client.post(
            "/v1/auth/login", json={"email": "ordering@example.com", "password": PASSWORD}
        )
        assert login.status_code == 200
        headers = {"x-csrf-token": client.cookies["numra_csrf"]}

        slow_commit["on"] = True

        created = await client.post(
            "/v1/people",
            json={
                "birth_first_names": "Ada",
                "birth_last_name": "Lovelace",
                "birth_date": "1990-01-01",
            },
            headers=headers,
        )
        assert created.status_code == 201, created.text
        person_id = created.json()["id"]

        follow_up = await client.get(f"/v1/people/{person_id}")
        assert follow_up.status_code == 200, (
            f"follow-up read got {follow_up.status_code}: the write's COMMIT had not "
            f"landed when its 201 was returned"
        )
