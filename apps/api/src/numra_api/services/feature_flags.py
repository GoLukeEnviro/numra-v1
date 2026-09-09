"""AVENYTH V2 Runtime-Feature-Flags (specs/v2/architecture.md "Feature flags").

Router-level FastAPI-Dependency-Factories, analog zum `assert_workspace_active`-Guard-
Idiom aus `services/workspace_guard.py` (PR-V2-10), hier aber sync und einmal PRO
ROUTER-KONSTRUKTION an `APIRouter(dependencies=[...])` angehaengt -- nicht Route-fuer-
Route wiederholt. In der Dependencies-Liste des jeweiligen Routers MUSS die Flag-
Dependency VOR jeder Auth-Dependency stehen, damit ein deaktiviertes Feature nicht mal
die "authenticated vs. nicht authenticated"-Unterscheidung leakt.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from fastapi import Depends

from numra_api.config import Settings
from numra_api.deps import get_settings_dep
from numra_api.services.errors import V2Disabled, V2PhaseDisabled

__all__ = ["require_v2_master", "require_v2_phase"]


def require_v2_master() -> Callable[..., None]:
    """Router-level FastAPI-Dependency. Prueft NUR den Master-Switch
    `AVENYTH_V2_ENABLED`. Siehe `workspace_guard.py` als analoges Guard-Idiom."""

    def _dependency(settings: Settings = Depends(get_settings_dep)) -> None:
        if not settings.avenyth_v2_enabled:
            raise V2Disabled()

    return _dependency


def require_v2_phase(
    flag_name: Literal[
        "connections",
        "relationship_workspaces",
        "checkins",
        "tasks",
        "copilot",
        "evidence_layer",
    ],
) -> Callable[..., None]:
    """Router-level FastAPI-Dependency. Prueft Master-Switch UND den Einzel-Flag
    (UND-Verknuepfung, Master gewinnt zuerst -- siehe Precedence-Test)."""

    def _dependency(settings: Settings = Depends(get_settings_dep)) -> None:
        if not settings.avenyth_v2_enabled:
            raise V2Disabled()
        if not getattr(settings, f"avenyth_{flag_name}_enabled"):
            raise V2PhaseDisabled(flag_name)

    return _dependency
