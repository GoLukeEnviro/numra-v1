"""GET /v1/health/ready runs a real, bounded-timeout check against every dependency
(database, deterministic engine, LLM provider, PDF service) instead of reading static
config flags — a config-only stub cannot tell a caller whether Postgres, Ollama, or the
PDF service is actually reachable right now. Results are cached for a short TTL
(`Settings.health_ready_cache_ttl_seconds`) on `app.state` so a tight poll loop (a
container orchestrator's readiness probe) doesn't hammer every dependency on every
request; each check is individually bounded by `Settings.health_check_timeout_seconds`
so one slow/hanging dependency can never make the endpoint itself hang.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import time
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.config import Settings
from numra_api.deps import get_db
from numra_api.services.llm_factory import build_llm_provider
from numra_numerology.engine import calculate_profile
from numra_numerology.models.person import PersonInput

router = APIRouter(prefix="/v1/health", tags=["health"])

HealthState = Literal["healthy", "degraded", "unhealthy", "disabled"]

#: A fixed, arbitrary sample input — this is a liveness probe for the engine module
#: itself (does it still import cleanly and compute without raising?), not a
#: correctness check; correctness is already covered by tests/golden fixtures.
_ENGINE_PROBE_PERSON = PersonInput(
    birth_first_names="Health", birth_last_name="Check", birth_date=dt.date(2000, 1, 1)
)
_ENGINE_PROBE_AS_OF_DATE = dt.date(2026, 1, 1)


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "live"}


async def _check_database(db: AsyncSession, *, timeout_seconds: float) -> HealthState:
    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=timeout_seconds)
    except Exception:  # noqa: BLE001 - health check must never raise
        return "unhealthy"
    return "healthy"


async def _check_engine() -> HealthState:
    try:
        calculate_profile(_ENGINE_PROBE_PERSON, _ENGINE_PROBE_AS_OF_DATE)
    except Exception:  # noqa: BLE001 - health check must never raise
        return "unhealthy"
    return "healthy"


#: ProviderHealth.status uses "unavailable" where this endpoint's vocabulary uses
#: "unhealthy" — everything else maps 1:1.
_PROVIDER_STATUS_TO_HEALTH_STATE: dict[str, HealthState] = {
    "healthy": "healthy",
    "degraded": "degraded",
    "unavailable": "unhealthy",
    "disabled": "disabled",
}


async def _check_llm(settings: Settings, *, timeout_seconds: float) -> HealthState:
    provider = build_llm_provider(settings)
    try:
        health = await asyncio.wait_for(provider.health(), timeout=timeout_seconds)
    except Exception:  # noqa: BLE001 - health check must never raise
        return "unhealthy"
    return _PROVIDER_STATUS_TO_HEALTH_STATE[health.status]


async def _check_pdf(settings: Settings, *, timeout_seconds: float) -> HealthState:
    if not settings.pdf_internal_url:
        return "disabled"
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(f"{settings.pdf_internal_url}/health/ready")
    except Exception:  # noqa: BLE001 - health check must never raise
        return "unhealthy"
    return "healthy" if response.status_code == 200 else "unhealthy"


def _overall_status(states: dict[str, HealthState]) -> Literal["healthy", "unhealthy"]:
    # The database is the only hard dependency: the app cannot serve any request
    # without it. LLM/PDF are optional/degradable subsystems — "disabled" or
    # "degraded" there does not make the whole service unready, matching
    # NUMRA_LLM_PROVIDER=disabled being a supported, healthy-by-design configuration.
    return "healthy" if states["database"] == "healthy" else "unhealthy"


@router.get("/ready")
async def ready(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    settings: Settings = request.app.state.settings

    cache: dict[str, Any] | None = getattr(request.app.state, "health_ready_cache", None)
    now = time.monotonic()
    if cache is not None and cache["expires_at"] > now:
        return dict(cache["payload"])

    timeout_seconds = settings.health_check_timeout_seconds
    database_status, engine_status, llm_status, pdf_status = await asyncio.gather(
        _check_database(db, timeout_seconds=timeout_seconds),
        _check_engine(),
        _check_llm(settings, timeout_seconds=timeout_seconds),
        _check_pdf(settings, timeout_seconds=timeout_seconds),
    )
    states: dict[str, HealthState] = {
        "database": database_status,
        "numerology_engine": engine_status,
        "llm": llm_status,
        "pdf": pdf_status,
    }

    payload: dict[str, Any] = {"status": _overall_status(states), **states}

    request.app.state.health_ready_cache = {
        "expires_at": now + settings.health_ready_cache_ttl_seconds,
        "payload": payload,
    }
    return payload
