"""AVENYTH V2 Runtime-Feature-Flags (specs/v2/architecture.md "Feature flags").

Router-level FastAPI-Dependency-Factories, analog zum `assert_workspace_active`-Guard-
Idiom aus `services/workspace_guard.py` (PR-V2-10), hier aber async und einmal PRO
ROUTER-KONSTRUKTION an `APIRouter(dependencies=[...])` angehaengt -- nicht Route-fuer-
Route wiederholt. In der Dependencies-Liste des jeweiligen Routers MUSS die Flag-
Dependency VOR jeder Auth-Dependency stehen, damit ein deaktiviertes Feature nicht mal
die "authenticated vs. nicht authenticated"-Unterscheidung leakt.

Datenquelle ist seit der Admin-Flag-Verwaltung die `feature_flags`-DB-Tabelle (ueber
den gecachten `FeatureFlagCache`, siehe `services/feature_flag_cache.py`), NICHT mehr
`Settings`/die `AVENYTH_*_ENABLED`-Env-Vars -- die Settings-Felder bleiben nur als
deprecated Seed-Default fuer die Migration bestehen (siehe `config.py`).
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, Literal

from fastapi import Depends

from numra_api.deps import get_feature_flag_cache
from numra_api.services.errors import V2Disabled, V2PhaseDisabled
from numra_api.services.feature_flag_cache import FeatureFlagCache

__all__ = ["require_v2_master", "require_v2_phase"]


def require_v2_master() -> Callable[..., Coroutine[Any, Any, None]]:
    """Router-level FastAPI-Dependency. Prueft NUR den Master-Switch (DB-Flag
    `v2_master`). Siehe `workspace_guard.py` als analoges Guard-Idiom."""

    async def _dependency(
        cache: FeatureFlagCache = Depends(get_feature_flag_cache),
    ) -> None:
        flags = await cache.get_all()
        if not flags.get("v2_master", False):
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
) -> Callable[..., Coroutine[Any, Any, None]]:
    """Router-level FastAPI-Dependency. Prueft Master-Switch UND den Einzel-Flag
    (UND-Verknuepfung, Master gewinnt zuerst -- siehe Precedence-Test)."""

    async def _dependency(
        cache: FeatureFlagCache = Depends(get_feature_flag_cache),
    ) -> None:
        flags = await cache.get_all()
        if not flags.get("v2_master", False):
            raise V2Disabled()
        if not flags.get(flag_name, False):
            raise V2PhaseDisabled(flag_name)

    return _dependency
