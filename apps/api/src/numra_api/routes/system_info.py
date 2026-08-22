from __future__ import annotations

from fastapi import APIRouter, Depends

from numra_api.config import Settings
from numra_api.deps import get_current_user, get_settings_dep
from numra_api.models import User
from numra_api.schemas.auth import SystemInfoOut

router = APIRouter(prefix="/v1/system-info", tags=["system-info"])


@router.get("", response_model=SystemInfoOut)
async def get_system_info(
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> SystemInfoOut:
    """V1.5 Epic N: sanitized system info for the Settings page. Auth-required (not
    a public endpoint) but still deliberately excludes every secret -- see
    SystemInfoOut's own docstring for exactly what is and isn't included."""
    return SystemInfoOut(
        environment=settings.environment,
        app_timezone=settings.app_timezone,
        session_ttl_hours=settings.session_ttl_hours,
        self_signup_enabled=settings.allow_self_signup,
        llm_provider=settings.numra_llm_provider,
        pdf_export_enabled=settings.pdf_internal_url is not None,
    )
