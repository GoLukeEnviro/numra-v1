from __future__ import annotations

from pydantic import BaseModel


class EntitlementSetOut(BaseModel):
    """The effective feature/limit bundle for the signed-in user (GET
    /v1/me/entitlements) -- either their explicit assignment or the seeded
    "beta_default" fallback (see repositories/entitlements.py). `max_connections`/
    `max_workspaces` of ``None`` means unlimited.

    D4: `relationship_copilot`, `advanced_relationship_analysis` and `premium_reports`
    are the EFFECTIVE values -- while `beta_gate_enforced` is true they are false for an
    account without a beta grant. `beta_access` says whether the account holds one
    (independent of whether the gate is currently enforced)."""

    personal_workspace: bool
    connections: bool
    relationship_workspaces: bool
    relationship_checkins: bool
    relationship_copilot: bool
    advanced_relationship_analysis: bool
    life_tracking: bool
    premium_reports: bool
    max_connections: int | None
    max_workspaces: int | None
    beta_access: bool
    beta_gate_enforced: bool
