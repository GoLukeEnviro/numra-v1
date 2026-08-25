from __future__ import annotations

from pydantic import BaseModel


class PublicConfigOut(BaseModel):
    """Bootstrap config for the pre-login web app (V1.6 B). Unauthenticated, so it may
    only carry what an anonymous visitor could already infer from the sign-in page
    itself -- deliberately no environment, URLs, paths, versions or any other
    deployment metadata (contrast SystemInfoOut, which is auth-required and says
    more). Any new field here is a new disclosure to the open internet."""

    self_signup_enabled: bool
    app_name: str
    supported_ui_locales: list[str]
