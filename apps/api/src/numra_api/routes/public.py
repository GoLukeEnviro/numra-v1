from __future__ import annotations

from fastapi import APIRouter, Depends

from numra_api.config import Settings
from numra_api.deps import get_settings_dep
from numra_api.schemas.public import PublicConfigOut

router = APIRouter(prefix="/v1/public", tags=["public"])

#: Compile-time constant rather than a Settings field -- unlike `app_brand_name`
#: below, the supported UI locale set is not a per-deployment branding choice, so it
#: stays a constant for the same reason it always has.
SUPPORTED_UI_LOCALES = ("de", "en")


@router.get("/config", response_model=PublicConfigOut)
async def get_public_config(
    settings: Settings = Depends(get_settings_dep),
) -> PublicConfigOut:
    """Unauthenticated by design: the sign-in page has to know whether self-signup is
    open before anyone can possibly hold a session.

    `app_name` deliberately comes from `settings.app_brand_name` even though this
    endpoint is unauthenticated -- a bounded, intentional exception to the "no
    Settings field on this route" rule that otherwise applies here (see
    PublicConfigOut's docstring): branding is not a security-relevant value the way
    `allow_self_signup` or a URL/secret would be, so a deployment configuring its own
    product name carries none of the risk that motivated keeping this route
    Settings-free in the first place."""
    return PublicConfigOut(
        self_signup_enabled=settings.allow_self_signup,
        app_name=settings.app_brand_name,
        supported_ui_locales=list(SUPPORTED_UI_LOCALES),
    )
