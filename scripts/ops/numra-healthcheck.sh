#!/usr/bin/env bash
# NUMRA readiness and job-health probe (agent0).
#
# Runs every five minutes from `numra-healthcheck.timer`. Checks the stacks this host
# runs, the freshness of the logical database backup and the job pipelines, writes a
# machine-readable status file and exits non-zero when something is wrong -- which marks
# the systemd unit failed, so `systemctl --failed` plus the status file are the
# operator-visible alarm.
#
# Alarm rules (deliberately narrow -- see docs/ops/numra-monitoring.md):
#   * readiness of a configured stack is not `healthy`            -> failure
#   * the job probe of a configured stack cannot read the database -> failure
#     (an unreadable pipeline is indistinguishable from a broken one)
#   * NEW failed jobs since the previous probe (per stack)         -> failure
#     The absolute number is NOT an alarm: a historical backlog from development would
#     otherwise alarm every five minutes forever.
#   * newest database dump older than 26 h                         -> failure
#
# Configuration: /etc/numra/healthcheck.env (optional, sourced if readable). Set
# `AUDIT_READY_URL=` to an empty value to stop probing the audit instance -- that is the
# documented switch for the PWA-10 teardown, so removing the stack cannot leave a
# permanently failed unit behind.
#
# Deliberately no secrets: every check reads a loopback HTTP endpoint, a directory
# listing or a database count. The stacks' env files are never read.
#
# Exit codes: 0 = all checks passed, 1 = at least one check failed.
set -uo pipefail

STATUS_FILE=/var/lib/numra/health-status.json
BACKUP_DIR=/var/lib/numra/backups
BACKUP_MAX_AGE_SECONDS=$((26 * 3600))
CONFIG_FILE=/etc/numra/healthcheck.env

# shellcheck disable=SC1090
[ -r "$CONFIG_FILE" ] && . "$CONFIG_FILE"

PROD_READY_URL=${PROD_READY_URL-http://127.0.0.1:17800/v1/health/ready}
PROD_DB_CONTAINER=${PROD_DB_CONTAINER-numra-prod-postgres-1}
AUDIT_READY_URL=${AUDIT_READY_URL-http://127.0.0.1:17801/v1/health/ready}
AUDIT_DB_CONTAINER=${AUDIT_DB_CONTAINER-numra-audit-postgres-1}

failures=()
lines=()

# --- helpers -------------------------------------------------------------------------

json_string() { printf '"%s"' "$(printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g')"; }

probe_readiness() {
  local name="$1" url="$2" body overall rc
  if [ -z "$url" ]; then
    lines+=("\"${name}_readiness\":\"not_configured\"")
    return 0
  fi
  body=$(curl -sf -m 10 "$url" 2>/dev/null)
  rc=$?
  if [ "$rc" -ne 0 ]; then
    failures+=("$name:readiness_unreachable")
    lines+=("\"${name}_readiness\":\"unreachable\"")
    return 0
  fi
  overall=$(printf '%s' "$body" | sed -n 's/.*"status":[[:space:]]*"\([a-z]*\)".*/\1/p')
  [ "$overall" = "healthy" ] || failures+=("$name:readiness_${overall:-unknown}")
  lines+=("\"${name}_readiness\":\"${overall:-unknown}\"")
}

# Job health. `previous` is the same stack's FAILED total from the last probe (-1 when
# unknown). Returns "" and records a failure when the database cannot be read.
probe_jobs() {
  local name="$1" container="$2" previous="$3" counts total window delta
  counts=$(docker exec -i "$container" psql -U numra -d numra -t -A -c \
    "select (select count(*) from report_jobs where status='FAILED') || ' ' ||
            (select count(*) from analysis_jobs where status='FAILED') || ' ' ||
            (select count(*) from report_jobs where status='FAILED'
               and updated_at > now() - interval '24 hours')" 2>/dev/null)
  if [ -z "$counts" ]; then
    failures+=("$name:jobs_unreadable")
    lines+=("\"${name}_failed_jobs\":null,\"${name}_failed_jobs_24h\":null")
    return 0
  fi
  total=$(printf '%s' "$counts" | awk '{print $1+$2}')
  window=$(printf '%s' "$counts" | awk '{print $3}')
  delta="unknown"
  if [ "$previous" -ge 0 ] 2>/dev/null; then
    delta=$((total - previous))
    if [ "$delta" -gt 0 ]; then
      failures+=("$name:${delta}_new_failed_job(s)")
    fi
  elif [ "$window" -gt 0 ]; then
    # No previous measurement to compare against (first run after a reset): fall back to
    # the 24h window, which is what a delta would have covered anyway.
    failures+=("$name:${window}_failed_job(s)_in_24h")
  fi
  lines+=("\"${name}_failed_jobs\":$total,\"${name}_failed_jobs_24h\":$window,\"${name}_new_failed_jobs\":\"$delta\"")
}

previous_total() {
  local key="$1" value
  value=$(python3 - "$STATUS_FILE" "$key" <<'PY' 2>/dev/null
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        print(json.load(handle).get(sys.argv[2], -1))
except Exception:
    print(-1)
PY
)
  printf '%s' "${value:--1}"
}

# --- checks --------------------------------------------------------------------------

prev_prod=$(previous_total prod_failed_jobs)
prev_audit=$(previous_total audit_failed_jobs)

probe_readiness prod "$PROD_READY_URL"
probe_jobs prod "$PROD_DB_CONTAINER" "$prev_prod"

probe_readiness audit "$AUDIT_READY_URL"
if [ -n "$AUDIT_READY_URL" ]; then
  probe_jobs audit "$AUDIT_DB_CONTAINER" "$prev_audit"
else
  lines+=("\"audit_failed_jobs\":null,\"audit_failed_jobs_24h\":null")
fi

newest_dump=$(ls -1t "$BACKUP_DIR"/numra-*.dump 2>/dev/null | head -1)
if [ -z "$newest_dump" ]; then
  failures+=("backup:no_dump_found")
  lines+=("\"backup_age_seconds\":null")
else
  age=$(( $(date +%s) - $(stat -c %Y "$newest_dump") ))
  lines+=("\"backup_age_seconds\":$age,\"backup_file\":$(json_string "$(basename "$newest_dump")")")
  [ "$age" -le "$BACKUP_MAX_AGE_SECONDS" ] || failures+=("backup:stale_${age}s")
fi

failure_json="[]"
if [ "${#failures[@]}" -gt 0 ]; then
  failure_json=$(printf '"%s",' "${failures[@]}")
  failure_json="[${failure_json%,}]"
fi

{
  printf '{"checked_at":"%s",' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  ( IFS=,; printf '%s' "${lines[*]}" )
  printf ',"failures":%s}\n' "$failure_json"
} > "$STATUS_FILE" 2>/dev/null || true

if [ "${#failures[@]}" -gt 0 ]; then
  echo "NUMRA healthcheck FAILED: ${failures[*]}" >&2
  exit 1
fi
echo "NUMRA healthcheck OK"
