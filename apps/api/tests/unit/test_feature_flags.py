"""services/feature_flags.py -- die Dependency-Callables werden direkt mit einem
`FeatureFlagCache`-Objekt aufgerufen (kein HTTP/echte DB noetig), dessen Loader einen
fixen Dict zurueckgibt -- die Cache-Mechanik selbst ist bereits in
test_feature_flag_cache.py getestet, hier geht es nur um die Guard-Logik/Precedence."""

from __future__ import annotations

import pytest

from numra_api.services.errors import V2Disabled, V2PhaseDisabled
from numra_api.services.feature_flag_cache import FeatureFlagCache
from numra_api.services.feature_flags import require_v2_master, require_v2_phase

pytestmark = pytest.mark.unit

_PHASES = [
    "connections",
    "relationship_workspaces",
    "checkins",
    "tasks",
    "copilot",
    "evidence_layer",
]


def _cache(**flags: bool) -> FeatureFlagCache:
    async def _loader() -> dict[str, bool]:
        return dict(flags)

    return FeatureFlagCache(loader=_loader)


# ---------------------------------------------------------------------------
# require_v2_master() isoliert
# ---------------------------------------------------------------------------


async def test_require_v2_master_blocks_when_false() -> None:
    dependency = require_v2_master()
    with pytest.raises(V2Disabled):
        await dependency(cache=_cache(v2_master=False))


async def test_require_v2_master_allows_when_true() -> None:
    dependency = require_v2_master()
    await dependency(cache=_cache(v2_master=True))  # darf nicht raisen


# ---------------------------------------------------------------------------
# require_v2_phase() -- pro Phase je 3 Tests, beweist die UND-Precedence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("phase", _PHASES)
async def test_require_v2_phase_blocks_when_phase_flag_false(phase: str) -> None:
    dependency = require_v2_phase(phase)  # type: ignore[arg-type]
    cache = _cache(v2_master=True, **{phase: False})
    with pytest.raises(V2PhaseDisabled) as excinfo:
        await dependency(cache=cache)
    assert excinfo.value.phase == phase


@pytest.mark.parametrize("phase", _PHASES)
async def test_require_v2_phase_allows_when_master_and_phase_true(phase: str) -> None:
    dependency = require_v2_phase(phase)  # type: ignore[arg-type]
    cache = _cache(v2_master=True, **{phase: True})
    await dependency(cache=cache)  # darf nicht raisen


@pytest.mark.parametrize("phase", _PHASES)
async def test_require_v2_phase_blocks_when_master_false_even_if_phase_true(
    phase: str,
) -> None:
    """Beweist die Precedence: Master gewinnt zuerst -- ein V2Disabled (nicht
    V2PhaseDisabled), obwohl der Einzel-Flag selbst an ist."""
    dependency = require_v2_phase(phase)  # type: ignore[arg-type]
    cache = _cache(v2_master=False, **{phase: True})
    with pytest.raises(V2Disabled):
        await dependency(cache=cache)


# ---------------------------------------------------------------------------
# Fehlender Flag-Key im Cache-Dict (DB-Zeile fehlt) -- fail closed, nicht raisen
# ---------------------------------------------------------------------------


async def test_require_v2_phase_blocks_when_flag_key_missing_entirely() -> None:
    dependency = require_v2_phase("copilot")
    cache = _cache(v2_master=True)  # "copilot"-Key fehlt im Dict
    with pytest.raises(V2PhaseDisabled):
        await dependency(cache=cache)
