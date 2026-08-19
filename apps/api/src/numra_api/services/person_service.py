from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from numra_api.services.errors import FutureBirthDateNotAllowed


def assert_birth_date_not_in_future(birth_date: dt.date, *, app_timezone: str) -> None:
    """Application-layer rule (canon-spec.md §30) — the engine itself has no concept of
    'today' and never performs this check; only this service does."""
    today_in_workspace_tz = dt.datetime.now(ZoneInfo(app_timezone)).date()
    if birth_date > today_in_workspace_tz:
        raise FutureBirthDateNotAllowed(
            f"birth_date {birth_date.isoformat()} is after {today_in_workspace_tz.isoformat()} "
            f"in {app_timezone}"
        )
