"""Versionierte Bootstrap-Profile fuer `python -m numra_api.cli flags init --profile`.

Jedes Profil nennt alle sieben Flags explizit. Profile wirken nur EINMAL pro
Datenbank (siehe `services/feature_flag_bootstrap.py`); spaetere Aenderungen laufen
ausschliesslich ueber `/admin/flags`.
"""

from __future__ import annotations

FLAG_NAMES: tuple[str, ...] = (
    "v2_master",
    "connections",
    "relationship_workspaces",
    "checkins",
    "tasks",
    "copilot",
    "evidence_layer",
)

_BETA_ON = frozenset({"v2_master", "connections", "relationship_workspaces", "copilot"})

PROFILES: dict[str, dict[str, bool]] = {
    # Frische Produktion ohne V2-Freigabe.
    "all-off": dict.fromkeys(FLAG_NAMES, False),
    # Heutiger Produktionsstand (Stand 2026-10-04).
    "beta": {name: name in _BETA_ON for name in FLAG_NAMES},
    # Audit-/Abnahme-Stack: alles an.
    "audit-all-on": dict.fromkeys(FLAG_NAMES, True),
}
