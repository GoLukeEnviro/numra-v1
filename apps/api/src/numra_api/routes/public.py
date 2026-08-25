from __future__ import annotations

from fastapi import APIRouter, Depends

from numra_api.config import Settings
from numra_api.deps import get_settings_dep
from numra_api.schemas.public import PublicConfigOut

router = APIRouter(prefix="/v1/public", tags=["public"])

#: Compile-time constants rather than Settings fields -- neither may become a channel
#: for deployment-specific values on an unauthenticated endpoint.
APP_NAME = "NUMRA"
SUPPORTED_UI_LOCALES = ("de", "en")


@router.get("/config", response_model=PublicConfigOut)
async def get_public_config(
    settings: Settings = Depends(get_settings_dep),
) -> PublicConfigOut:
    """Unauthenticated by design: the sign-in page has to know whether self-signup is
    open before anyone can possibly hold a session."""
    return PublicConfigOut(
        self_signup_enabled=settings.allow_self_signup,
        app_name=APP_NAME,
        supported_ui_locales=list(SUPPORTED_UI_LOCALES),
    )
