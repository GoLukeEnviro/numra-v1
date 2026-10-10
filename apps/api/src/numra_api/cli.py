"""Admin management CLI. Invoked as::

    uv run python -m numra_api.cli admin promote-admin --email <email>
    uv run python -m numra_api.cli admin list
    uv run python -m numra_api.cli flags init [--profile <name>] [--dry-run]
    uv run python -m numra_api.cli beta inventory [--since-days N]
    uv run python -m numra_api.cli beta backfill [--since-days N] [--apply]

Stdlib `argparse` only -- no new dependency, no new pyproject entrypoint (keeps this
release's footprint minimal). Reuses the app's existing Settings/engine/sessionmaker
construction (`config.get_settings`, `db.build_engine`/`build_sessionmaker`) rather
than reinventing DB connection setup.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import os
import sys

from sqlalchemy import select

from numra_api.config import get_settings
from numra_api.db import build_engine, build_sessionmaker
from numra_api.feature_flag_profiles import PROFILES
from numra_api.models import User
from numra_api.models.enums import AuditAction, UserRole
from numra_api.repositories.audit import record_audit_event
from numra_api.repositories.users import get_user_by_email, set_user_role
from numra_api.services.beta_inventory import UsageRow, backfill_beta_access, collect_usage
from numra_api.services.feature_flag_bootstrap import ProfileRequiredError, bootstrap_flags


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
            user = await get_user_by_email(db, email=email)
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


async def init_flags(profile: str | None, dry_run: bool = False) -> int:
    """Einmaliger Flag-Bootstrap. No-op (Exit 0), sobald ein Bootstrap-Status existiert --
    auch bei anderem oder ohne Profil. Fehlt der Status, ist ein Profil Pflicht (Exit 2,
    nichts geschrieben). Mit `dry_run` werden Status und Diff nur angezeigt."""
    settings = get_settings()
    engine = build_engine(settings.database_url)
    sessionmaker = build_sessionmaker(engine)
    try:
        try:
            async with sessionmaker() as db:
                result = await bootstrap_flags(db, profile=profile, dry_run=dry_run)
        except (ProfileRequiredError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        if result.status_source is None:
            print(f"bootstrap status: missing (profile {profile!r})")
        else:
            print(f"bootstrap status: {result.status_source} (profile {result.profile!r})")
        for change in result.changes:
            print(f"  {change.name}: {change.before} -> {change.after}")
        if dry_run:
            print("dry-run: nothing written")
        elif result.applied:
            print(f"applied profile {profile!r}")
        else:
            print("no-op: bootstrap already done, nothing changed")
        return 0
    finally:
        await engine.dispose()


def _since(days: int | None) -> dt.datetime | None:
    return dt.datetime.now(dt.UTC) - dt.timedelta(days=days) if days else None


def _print_usage(rows: list[UsageRow]) -> None:
    print(f"accounts with usage: {len(rows)}  (already granted: {sum(r.granted for r in rows)})")
    print("pseudonym     reports analyses patterns copilot active granted")
    for r in rows:
        print(
            f"{r.pseudonym:<13} {r.reports:>7} {r.analyses:>8} {r.patterns:>8} "
            f"{r.copilot_messages:>7} {r.is_active!s:>6} {r.granted!s:>7}"
        )


async def beta_inventory(since_days: int | None) -> int:
    """Read-only: counters per account as HMAC pseudonyms, no content, no e-mail."""
    settings = get_settings()
    engine = build_engine(settings.database_url)
    sessionmaker = build_sessionmaker(engine)
    try:
        async with sessionmaker() as db:
            rows = await collect_usage(db, secret=settings.session_secret, since=_since(since_days))
            await db.rollback()
        _print_usage(rows)
        return 0
    finally:
        await engine.dispose()


async def beta_backfill(since_days: int | None, apply: bool) -> int:
    """Grants beta access to active accounts that used a cost-intensive feature.
    Dry-run unless ``apply``; never run by a migration or at startup."""
    settings = get_settings()
    engine = build_engine(settings.database_url)
    sessionmaker = build_sessionmaker(engine)
    try:
        async with sessionmaker() as db:
            rows = await collect_usage(db, secret=settings.session_secret, since=_since(since_days))
            run_label = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
            result = await backfill_beta_access(db, rows=rows, apply=apply, run_label=run_label)
            if apply:
                await db.commit()
            else:
                await db.rollback()
        for r in rows:
            if r.is_active and not r.granted:
                print(f"{'grant' if apply else 'would grant'}: {r.pseudonym}")
        print(
            f"candidates={result.candidates} granted={result.granted} "
            f"already_granted={result.already_granted}"
        )
        if not apply:
            print("dry-run: nothing written (use --apply to grant)")
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

    flags_parser = subparsers.add_parser("flags", help="feature-flag bootstrap")
    flags_subparsers = flags_parser.add_subparsers(dest="flags_command", required=True)
    init_parser = flags_subparsers.add_parser(
        "init", help="set initial flag values once from a versioned profile"
    )
    init_parser.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        default=os.environ.get("NUMRA_FLAGS_PROFILE") or None,
        help="required while no bootstrap status exists; default: $NUMRA_FLAGS_PROFILE",
    )
    init_parser.add_argument("--dry-run", action="store_true")

    beta_parser = subparsers.add_parser("beta", help="closed-beta transition (D4)")
    beta_subparsers = beta_parser.add_subparsers(dest="beta_command", required=True)
    inventory_parser = beta_subparsers.add_parser(
        "inventory", help="read-only usage counters per account (pseudonymous)"
    )
    inventory_parser.add_argument("--since-days", type=int, default=None)
    backfill_parser = beta_subparsers.add_parser(
        "backfill", help="grant beta access to accounts that already use the features"
    )
    backfill_parser.add_argument("--since-days", type=int, default=None)
    backfill_parser.add_argument(
        "--apply", action="store_true", help="write the grants (default: dry-run)"
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "admin" and args.admin_command == "promote-admin":
        return asyncio.run(promote_admin(args.email))
    if args.command == "admin" and args.admin_command == "list":
        return asyncio.run(list_admins())
    if args.command == "flags" and args.flags_command == "init":
        return asyncio.run(init_flags(args.profile, args.dry_run))

    if args.command == "beta" and args.beta_command == "inventory":
        return asyncio.run(beta_inventory(args.since_days))
    if args.command == "beta" and args.beta_command == "backfill":
        return asyncio.run(beta_backfill(args.since_days, args.apply))

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
