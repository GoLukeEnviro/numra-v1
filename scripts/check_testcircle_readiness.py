"""Check HTTP health and backup freshness without changing either system."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path


def response_is_healthy(name: str, status_code: int, body: object) -> bool:
    if status_code != 200 or not isinstance(body, dict):
        return False
    return name != "readiness" or body.get("status") == "healthy"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--max-backup-age-hours", type=float, default=24)
    parser.add_argument("--timeout-seconds", type=float, default=10)
    args = parser.parse_args()

    checks: dict[str, object] = {}
    ok = True
    for name, path in (("liveness", "/v1/health/live"), ("readiness", "/v1/health/ready")):
        try:
            with urllib.request.urlopen(
                args.base_url.rstrip("/") + path, timeout=args.timeout_seconds
            ) as response:
                body = json.load(response)
                healthy = response_is_healthy(name, response.status, body)
                checks[name] = {
                    "ok": healthy,
                    "status": response.status,
                    "body": body,
                }
                ok &= healthy
        except Exception as exc:  # command reports the operational failure verbatim
            checks[name] = {"ok": False, "error": str(exc)}
            ok = False

    if args.backup.is_file():
        age_hours = (time.time() - args.backup.stat().st_mtime) / 3600
        fresh = age_hours <= args.max_backup_age_hours
        checks["backup"] = {"ok": fresh, "age_hours": round(age_hours, 3)}
        ok &= fresh
    else:
        checks["backup"] = {"ok": False, "error": "backup file does not exist"}
        ok = False

    print(json.dumps({"ok": ok, "checks": checks}, ensure_ascii=False, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
