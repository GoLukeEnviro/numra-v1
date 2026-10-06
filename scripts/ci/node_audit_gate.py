"""Bewertet `pnpm audit --prod --json` fuer genau einen Workspace-Pfad.

Fail-closed: ungueltige/unvollstaendige Audit-Ausgabe, jedes High/Critical-Advisory
im Workspace ohne gueltige Ausnahme und jede abgelaufene Ausnahme beenden mit Exit 1.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

GATED_SEVERITIES = {"high", "critical"}
REQUIRED_FIELDS = ("id", "package", "path", "reason", "expires")


def load_audit(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"FAIL: Audit-Ausgabe nicht lesbar ({exc})") from exc
    if not isinstance(data, dict) or "advisories" not in data or "metadata" not in data:
        raise SystemExit(
            "FAIL: Audit-Ausgabe ohne advisories/metadata (Audit-Endpoint nicht erreichbar?)"
        )
    return data


def load_exceptions(path: Path | None, workspace: str) -> list[dict]:
    if path is None:
        return []
    import yaml

    entries = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("exceptions") or []
    for entry in entries:
        missing = [f for f in REQUIRED_FIELDS if not entry.get(f)]
        if missing:
            raise SystemExit(f"FAIL: Ausnahme {entry.get('id', '?')} ohne Pflichtfelder {missing}")
        if entry["path"] != workspace:
            raise SystemExit(
                f"FAIL: Ausnahme {entry['id']} gilt fuer {entry['path']}, nicht fuer {workspace}"
            )
    return entries


def workspace_findings(audit: dict, workspace: str) -> dict[str, dict]:
    prefix = f"{workspace} > "
    found: dict[str, dict] = {}
    for advisory in audit["advisories"].values():
        if advisory.get("severity") not in GATED_SEVERITIES:
            continue
        all_paths = [p for f in advisory.get("findings", []) for p in f.get("paths", [])]
        if not all_paths:
            raise SystemExit(
                f"FAIL: {advisory['github_advisory_id']} ohne Abhaengigkeitspfade -- "
                "pnpm audit lief ohne vorheriges pnpm install, Zuordnung zum Workspace unmoeglich"
            )
        paths = [p for p in all_paths if p.startswith(prefix)]
        if paths:
            found[advisory["github_advisory_id"]] = {
                "package": advisory["module_name"],
                "severity": advisory["severity"],
            }
    return found


def evaluate(audit: dict, workspace: str, exceptions: list[dict], today: dt.date) -> list[str]:
    errors: list[str] = []
    expired = {e["id"] for e in exceptions if _expiry(e) < today}
    for entry in exceptions:
        if entry["id"] in expired:
            errors.append(
                f"Ausnahme {entry['id']} ({entry['package']}) abgelaufen am {_expiry(entry)}"
            )
    allowed = {e["id"] for e in exceptions} - expired
    for advisory_id, info in sorted(workspace_findings(audit, workspace).items()):
        if advisory_id in expired:
            continue
        if advisory_id not in allowed:
            errors.append(
                f"Neuer {info['severity']}-Befund {advisory_id} ({info['package']}) in {workspace}"
            )
    return errors


def _expiry(entry: dict) -> dt.date:
    value = entry["expires"]
    return value if isinstance(value, dt.date) else dt.date.fromisoformat(str(value))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-json", type=Path, required=True)
    parser.add_argument("--workspace", required=True, help="z. B. apps/web")
    parser.add_argument("--exceptions", type=Path)
    parser.add_argument(
        "--today", type=dt.date.fromisoformat, default=dt.datetime.now(dt.UTC).date()
    )
    args = parser.parse_args()

    audit = load_audit(args.audit_json)
    exceptions = load_exceptions(args.exceptions, args.workspace)
    errors = evaluate(audit, args.workspace, exceptions, args.today)
    if errors:
        print("\n".join(f"FAIL: {e}" for e in errors))
        return 1
    covered = sorted(workspace_findings(audit, args.workspace))
    print(
        f"OK: {args.workspace} ohne ungedeckte High/Critical-Befunde; "
        f"gueltige Ausnahmen genutzt: {covered}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
