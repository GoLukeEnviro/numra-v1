from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import AdminAuditEvent
from numra_api.models.enums import AuditAction
from numra_api.schemas.admin import AuditEventOut


async def record_audit_event(
    db: AsyncSession,
    *,
    actor_user_id: uuid.UUID | None,
    action: AuditAction,
    target_user_id: uuid.UUID | None,
    safe_metadata: dict[str, Any] | None = None,
) -> AdminAuditEvent:
    """Caller commits (matches the existing repository idiom -- see
    `repositories/users.py::create_user`). `safe_metadata` must never contain a
    password, session token, or password hash -- non-secret context only."""
    event = AdminAuditEvent(
        actor_user_id=actor_user_id,
        action=str(action),
        target_user_id=target_user_id,
        safe_metadata=safe_metadata or {},
    )
    db.add(event)
    await db.flush()
    return event


def _to_out(event: AdminAuditEvent) -> AuditEventOut:
    return AuditEventOut(
        id=str(event.id),
        actor_user_id=str(event.actor_user_id) if event.actor_user_id else None,
        action=event.action,
        target_user_id=str(event.target_user_id) if event.target_user_id else None,
        safe_metadata=event.safe_metadata,
        created_at=event.created_at,
    )


async def list_audit_events_paginated(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    action: AuditAction | None = None,
    target_user_id: uuid.UUID | None = None,
) -> tuple[list[AuditEventOut], int]:
    filters: list[ColumnElement[bool]] = []
    if action is not None:
        filters.append(AdminAuditEvent.action == str(action))
    if target_user_id is not None:
        filters.append(AdminAuditEvent.target_user_id == target_user_id)

    count_stmt = select(func.count()).select_from(AdminAuditEvent)
    list_stmt = select(AdminAuditEvent).order_by(AdminAuditEvent.created_at.desc())
    if filters:
        count_stmt = count_stmt.where(*filters)
        list_stmt = list_stmt.where(*filters)
    list_stmt = list_stmt.offset((page - 1) * page_size).limit(page_size)

    total = (await db.execute(count_stmt)).scalar_one()
    events = list((await db.execute(list_stmt)).scalars().all())
    return [_to_out(e) for e in events], total
