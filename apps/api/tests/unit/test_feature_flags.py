"""services/feature_flags.py -- die Dependency-Callables werden direkt mit einem
`Settings(...)`-Objekt aufgerufen (kein HTTP/DB noetig), da sie synchron sind und
`Depends(get_settings_dep)` beim direkten Aufruf einfach das positionelle Argument
entgegennimmt."""

from __future__ import annotations

import pytest

from numra_api.config import Settings
from numra_api.services.errors import V2Disabled, V2PhaseDisabled
from numra_api.services.feature_flags import require_v2_master, require_v2_phase

pytestmark = pytest.mark.unit

_DB_URL = "postgresql+asyncpg://numra:numra_dev_password@127.0.0.1:5432/numra_test"

_PHASES = [
    "connections",
    "relationship_workspaces",
    "checkins",
    "tasks",
    "copilot",
    "evidence_layer",
]


def _settings(**overrides: bool) -> Settings:
    return Settings(database_url=_DB_URL, **overrides)


# ---------------------------------------------------------------------------
# require_v2_master() isoliert
# ---------------------------------------------------------------------------


def test_require_v2_master_blocks_when_false() -> None:
    dependency = require_v2_master()
    with pytest.raises(V2Disabled):
        dependency(settings=_settings(avenyth_v2_enabled=False))


def test_require_v2_master_allows_when_true() -> None:
    dependency = require_v2_master()
    dependency(settings=_settings(avenyth_v2_enabled=True))  # darf nicht raisen


# ---------------------------------------------------------------------------
# require_v2_phase() -- pro Phase je 3 Tests, beweist die UND-Precedence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("phase", _PHASES)
def test_require_v2_phase_blocks_when_phase_flag_false(phase: str) -> None:
    dependency = require_v2_phase(phase)  # type: ignore[arg-type]
    settings = _settings(avenyth_v2_enabled=True, **{f"avenyth_{phase}_enabled": False})
    with pytest.raises(V2PhaseDisabled) as excinfo:
        dependency(settings=settings)
    assert excinfo.value.phase == phase


@pytest.mark.parametrize("phase", _PHASES)
def test_require_v2_phase_allows_when_master_and_phase_true(phase: str) -> None:
    dependency = require_v2_phase(phase)  # type: ignore[arg-type]
    settings = _settings(avenyth_v2_enabled=True, **{f"avenyth_{phase}_enabled": True})
    dependency(settings=settings)  # darf nicht raisen


@pytest.mark.parametrize("phase", _PHASES)
def test_require_v2_phase_blocks_when_master_false_even_if_phase_true(phase: str) -> None:
    """Beweist die Precedence: Master gewinnt zuerst -- ein V2Disabled (nicht
    V2PhaseDisabled), obwohl der Einzel-Flag selbst an ist."""
    dependency = require_v2_phase(phase)  # type: ignore[arg-type]
    settings = _settings(avenyth_v2_enabled=False, **{f"avenyth_{phase}_enabled": True})
    with pytest.raises(V2Disabled):
        dependency(settings=settings)
