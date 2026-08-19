from __future__ import annotations

import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import Session, User


async def delete_all_user_data(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    """Cascading account deletion (master prompt §137-§138).

    Every child table (`people`, `name_identities`, `calculations`,
    `relationships`, `reports`, `report_sections`, `report_jobs`,
    `llm_generations`, `exports`) has ``ondelete="CASCADE"`` on its foreign key
    to `users` (directly or transitively through `people`/`calculations`/
    `reports`/`report_jobs` — see models/tables.py), so deleting the `User` row
    is sufficient: the database itself removes every dependent row. Sessions are
    deleted explicitly first only so a caller's own current session is gone
    immediately, before the user row deletion cascades to it anyway.
    """
    await db.execute(delete(Session).where(Session.user_id == user_id))
    await db.execute(delete(User).where(User.id == user_id))
