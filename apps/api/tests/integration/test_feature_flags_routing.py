"""AVENYTH V2 Runtime-Feature-Flags -- echte HTTP-Calls gegen die Router-level-Guards
aus services/feature_flags.py. Baut bewusst eigene `Settings`/`create_app`-Instanzen
statt der `app`/`client`-Fixtures (dieselbe Technik wie test_health.py /
test_email_verification.py), weil die Standard-`settings`-Fixture alle 7 Flags fest auf
True setzt (siehe conftest.py) -- hier muss genau EIN Flag pro Testfall abweichen.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from numra_api.app import create_app
from numra_api.auth.passwords import hash_password
from numra_api.config import Settings
from numra_api.db import build_sessionmaker
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration

# Repraesentativer, mit einem frisch angemeldeten (aber sonst leeren) Nutzer sofort
# erreichbarer GET-Endpoint pro Phase -- kein Workspace/Person/Custom-Setup noetig,
# weil der Guard bereits VOR jeder Route-Logik greift bzw. der Happy-Path selbst nur
# eine leere Liste liefert.
_PHASE_ENDPOINT = {
    "connections": "/v1/connections/invitations",
    "relationship_workspaces": "/v1/workspaces",
    "checkins": "/v1/workspaces/00000000-0000-0000-0000-000000000000/checkin-template",
    "tasks": "/v1/workspaces/00000000-0000-0000-0000-000000000000/tasks",
    "copilot": "/v1/workspaces/00000000-0000-0000-0000-000000000000/copilot/threads",
    "evidence_layer": "/v1/people/00000000-0000-0000-0000-000000000000/evidence-results"
    "?metric_key=mood&correlation_target=PERSONAL_DAY&correlation_target_value=1",
}

_ALL_TRUE = {
    "avenyth_v2_enabled": True,
    "avenyth_connections_enabled": True,
    "avenyth_relationship_workspaces_enabled": True,
    "avenyth_checkins_enabled": True,
    "avenyth_tasks_enabled": True,
    "avenyth_copilot_enabled": True,
    "avenyth_evidence_layer_enabled": True,
}


def _flags(**overrides: bool) -> dict[str, bool]:
    flags = dict(_ALL_TRUE)
    flags.update(overrides)
    return flags


async def _build_client(settings: Settings, db_engine, flag_overrides: dict[str, bool]):
    scoped_settings = Settings(
        database_url=settings.database_url,
        environment="test",
        numra_llm_provider="mock",
        **flag_overrides,
    )
    app = create_app(settings=scoped_settings)
    app.state.engine = db_engine
    app.state.sessionmaker = build_sessionmaker(db_engine)
    return app


async def _login(app, email: str) -> tuple[AsyncClient, dict]:
    async with app.state.sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password("password12345"))
        await db.commit()
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
    response = await client.post(
        "/v1/auth/login", json={"email": email, "password": "password12345"}
    )
    assert response.status_code == 200
    return client, {"x-csrf-token": client.cookies["numra_csrf"]}


# ---------------------------------------------------------------------------
# Pro Phase: 503 wenn deaktiviert, normaler Betrieb wenn aktiviert
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("phase", sorted(_PHASE_ENDPOINT))
async def test_phase_returns_503_when_disabled(phase: str, settings: Settings, db_engine) -> None:
    app = await _build_client(settings, db_engine, _flags(**{f"avenyth_{phase}_enabled": False}))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        response = await c.get(_PHASE_ENDPOINT[phase])
    assert response.status_code == 503
    assert response.json()["code"] == "V2_PHASE_DISABLED"


@pytest.mark.parametrize("phase", sorted(_PHASE_ENDPOINT))
async def test_phase_works_normally_when_enabled(phase: str, settings: Settings, db_engine) -> None:
    """Smoke-Test: der Guard bricht den Happy-Path nicht -- ein authentifizierter
    Aufruf erreicht die eigentliche Route-Logik (kein 503 mehr, egal welchen anderen
    Status der leere/nicht-existente Datensatz sonst zurueckgibt)."""
    app = await _build_client(settings, db_engine, _flags())
    client, headers = await _login(app, f"flag-{phase}@example.com")
    try:
        response = await client.get(_PHASE_ENDPOINT[phase], headers=headers)
    finally:
        await client.aclose()
    assert response.status_code != 503


# ---------------------------------------------------------------------------
# Master-Switch -- Precedence End-to-End ueber mehrere Phasen hinweg
# ---------------------------------------------------------------------------


async def test_v2_master_switch_blocks_all_phases_when_false(settings: Settings, db_engine) -> None:
    app = await _build_client(settings, db_engine, _flags(avenyth_v2_enabled=False))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        for phase, endpoint in _PHASE_ENDPOINT.items():
            response = await c.get(endpoint)
            assert response.status_code == 503, phase
            assert response.json()["code"] == "V2_DISABLED", phase


async def test_personal_workspace_routes_gated_by_master_only(
    settings: Settings, db_engine
) -> None:
    """workspace.py/private_notes.py/private_reflections.py/personal_tasks.py haengen
    NUR an require_v2_master() -- kein Phase-Flag kann sie einzeln abschalten."""
    disabled_app = await _build_client(settings, db_engine, _flags(avenyth_v2_enabled=False))
    async with AsyncClient(
        transport=ASGITransport(app=disabled_app), base_url="http://testserver"
    ) as c:
        response = await c.get("/v1/me/workspace")
    assert response.status_code == 503
    assert response.json()["code"] == "V2_DISABLED"

    enabled_app = await _build_client(settings, db_engine, _flags())
    client, headers = await _login(enabled_app, "personal-workspace-master@example.com")
    try:
        response = await client.get("/v1/me/workspace", headers=headers)
    finally:
        await client.aclose()
    assert response.status_code != 503
