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

    llm_status = (
        "healthy" if settings.numra_llm_enabled and settings.ollama_base_url else "degraded"
    )

    overall = "healthy" if database_status == "healthy" else "unhealthy"

    return {
        "status": overall,
        "database": database_status,
        "numerology_engine": "healthy",
        "llm": llm_status,
        "pdf": "healthy",
    }
