"""Admin management CLI. Invoked as::

    uv run python -m numra_api.cli admin promote-admin --email <email>
    uv run python -m numra_api.cli admin list

Stdlib `argparse` only -- no new dependency, no new pyproject entrypoint (keeps this
release's footprint minimal). Reuses the app's existing Settings/engine/sessionmaker
construction (`config.get_settings`, `db.build_engine`/`build_sessionmaker`) rather
than reinventing DB connection setup.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from numra_api.config import get_settings
from numra_api.db import build_engine, build_sessionmaker
from numra_api.models import User
from numra_api.models.enums import AuditAction, UserRole
from numra_api.repositories.audit import record_audit_event
from numra_api.repositories.users import get_user_by_email_normalized, set_user_role


async def promote_admin(email: str) -> int:
    """Idempotent: looks up an existing user by (normalized) email and promotes them
    to ADMIN. NEVER creates a user -- if no account with this email exists, this
    exits non-zero and touches nothing. A no-op (exit 0, message only) if the user is
    already an admin. Never touches the password."""
    settings = get_settings()
    engine = build_engine(settings.database_url)
    sessionmaker = build_sessionmaker(engine)
    try:
        async with sessionmaker() as db:
            user = await get_user_by_email_normalized(db, email=email)
            if user is None:
                print(f"no user found with email {email!r} -- not creating one")
                return 1
            if user.role == UserRole.ADMIN:
                print(f"{user.email} is already ADMIN")
                await db.commit()
                return 0
            await set_user_role(db, user=user, role=UserRole.ADMIN)
            await record_audit_event(
                db,
                actor_user_id=None,
                action=AuditAction.ADMIN_PROMOTED,
                target_user_id=user.id,
                safe_metadata={"promoted_via": "cli"},
            )
            await db.commit()
            print(f"promoted {user.email} to ADMIN")
            return 0
    finally:
        await engine.dispose()


async def list_admins() -> int:
    settings = get_settings()
    engine = build_engine(settings.database_url)
    sessionmaker = build_sessionmaker(engine)
    try:
        async with sessionmaker() as db:
            result = await db.execute(select(User).where(User.role == UserRole.ADMIN))
            admins = list(result.scalars().all())
            if not admins:
                print("no admins found")
            for admin in admins:
                print(f"{admin.email}  ({admin.id})")
            return 0
    finally:
        await engine.dispose()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="numra_api.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    admin_parser = subparsers.add_parser("admin", help="admin account management")
    admin_subparsers = admin_parser.add_subparsers(dest="admin_command", required=True)

    promote_parser = admin_subparsers.add_parser(
        "promote-admin", help="promote an existing user to ADMIN"
    )
    promote_parser.add_argument("--email", required=True)

    admin_subparsers.add_parser("list", help="list all ADMIN users")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "admin" and args.admin_command == "promote-admin":
        return asyncio.run(promote_admin(args.email))
    if args.command == "admin" and args.admin_command == "list":
        return asyncio.run(list_admins())

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
