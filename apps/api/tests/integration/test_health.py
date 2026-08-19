from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_live(client) -> None:
    response = await client.get("/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "live"}


async def test_ready(client) -> None:
    response = await client.get("/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["database"] == "healthy"
    assert body["numerology_engine"] == "healthy"
    assert body["llm"] == "degraded"
