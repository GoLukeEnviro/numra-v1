"""Echte PostgreSQL-Transaktionen: Grant gegen Dissolve, jeweils mit bewiesenem
Blocking (siehe test_checkin_concurrency._overlap). Ergebnis in beiden Reihenfolgen:
nach dem Dissolve existiert kein aktiver Grant mehr."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from test_checkin_concurrency import _overlap
from test_checkins import _connect

from numra_api.models import ConsentGrant, RelationshipWorkspace, User
from numra_api.services.connection_service import dissolve_own_connection
from numra_api.services.consent_service import grant_consent

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("dissolve_first", [True, False])
async def test_grant_against_dissolve_leaves_no_active_grant(client, sessionmaker, dissolve_first):
    wid = uuid.UUID(
        await _connect(client, sessionmaker, "crace-a@example.com", "crace-b@example.com")
    )
    async with sessionmaker() as db:
        users = {u.email: u.id for u in (await db.scalars(select(User))).all()}
        connection_id = (await db.get(RelationshipWorkspace, wid)).connection_id
    a, b = users["crace-a@example.com"], users["crace-b@example.com"]

    async def dissolve(db):
        return await dissolve_own_connection(db, connection_id=connection_id, user_id=b)

    async def grant(db):
        return await grant_consent(db, workspace_id=wid, grantor_user_id=a, scope="PRIVATE_JOURNAL")

    _, second = await _overlap(
        sessionmaker, dissolve if dissolve_first else grant, grant if dissolve_first else dissolve
    )
    if dissolve_first:
        assert second == "WORKSPACE_DISSOLVED"
    else:
        assert second.status == "DISSOLVED"
    async with sessionmaker() as db:
        grants = (
            await db.scalars(select(ConsentGrant).where(ConsentGrant.workspace_id == wid))
        ).all()
    assert [g for g in grants if g.revoked_at is None] == []
