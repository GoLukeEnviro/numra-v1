from __future__ import annotations

import datetime as dt

import pytest

from numra_api.auth.passwords import hash_password
from numra_api.models.enums import (
    AnalysisJobStatus,
    AnalysisType,
    InvitationMethod,
    InvitationState,
)
from numra_api.models.tables import AnalysisJob, ConnectionInvitation, UserConnection
from numra_api.repositories.admin import compute_admin_stats
from numra_api.repositories.users import create_user
from numra_api.repositories.workspaces import create_relationship_workspace

pytestmark = pytest.mark.integration


async def test_admin_stats_includes_v2_health(sessionmaker) -> None:
    now = dt.datetime.now(dt.UTC)
    async with sessionmaker() as db:
        inviter = await create_user(
            db, email="v2health-inviter@example.com", password_hash=hash_password("password12345")
        )
        user_a = await create_user(
            db, email="v2health-a@example.com", password_hash=hash_password("password12345")
        )
        user_b = await create_user(
            db, email="v2health-b@example.com", password_hash=hash_password("password12345")
        )
        await db.flush()

        db.add(
            ConnectionInvitation(
                inviter_user_id=inviter.id,
                method=InvitationMethod.LINK,
                token_hash="x" * 64,
                state=InvitationState.PENDING,
                expires_at=now + dt.timedelta(days=7),
            )
        )

        connection = UserConnection(user_a_id=user_a.id, user_b_id=user_b.id)
        db.add(connection)
        await db.flush()
        workspace = await create_relationship_workspace(db, connection_id=connection.id)

        db.add(
            AnalysisJob(
                workspace_id=workspace.id,
                requested_by_user_id=user_a.id,
                analysis_type=AnalysisType.RELATIONSHIP_INTERPRETATION,
                status=AnalysisJobStatus.QUEUED,
                created_at=now - dt.timedelta(minutes=20),
            )
        )
        stale_failed = AnalysisJob(
            workspace_id=workspace.id,
            requested_by_user_id=user_a.id,
            analysis_type=AnalysisType.SHADOW_DYNAMICS,
            status=AnalysisJobStatus.FAILED,
        )
        db.add(stale_failed)
        await db.commit()

        stats = await compute_admin_stats(db, now=now)

    assert stats.v2.invitations_pending == 1
    assert stats.v2.connections_active == 1
    assert stats.v2.workspaces_active == 1
    assert stats.v2.analysis_queued_gt_15min == 1
    assert stats.v2.analysis_failed_24h == 1
