from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.config import Settings
from numra_api.deps import get_db

router = APIRouter(prefix="/v1/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "live"}


@router.get("/ready")
async def ready(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    settings: Settings = request.app.state.settings

    try:
        await db.execute(text("SELECT 1"))
        database_status = "healthy"
    except Exception:  # noqa: BLE001 - health check must not raise
        database_status = "unhealthy"

    # NOTE: still a config-only stub, not a real provider health check — see task
    # P1 "truthful health checks" (specs/evidence/final-hardening-baseline.md) for the
    # planned replacement that actually calls llm.health()/db/pdf with bounded timeouts.
    llm_status = (
        "healthy"
        if settings.numra_llm_provider == "ollama" and settings.ollama_base_url
        else "degraded"
        if settings.numra_llm_provider == "mock"
        else "disabled"
    )

    overall = "healthy" if database_status == "healthy" else "unhealthy"

    return {
        "status": overall,
        "database": database_status,
        "numerology_engine": "healthy",
        "llm": llm_status,
        "pdf": "healthy",
    }
