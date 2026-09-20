#!/usr/bin/env bash
# NUMRA readiness and job-health probe (agent0).
#
# Runs every five minutes from `numra-healthcheck.timer`. Checks the two stacks this
# host runs (production on :17800, the isolated audit instance on :17801) and the
# freshness of the logical database backup, writes a machine-readable status file and
# exits non-zero when something is wrong -- which makes the systemd unit fail, so
# `systemctl --failed` is the operator-visible signal.
#
# Deliberately no secrets: every check reads a loopback HTTP endpoint or a file name,
# never an environment value. The stacks' env files are not touched.
#
# Exit codes: 0 = all checks passed, 1 = at least one check failed.
set -uo pipefail

STATUS_FILE=/var/lib/numra/health-status.json
BACKUP_DIR=/var/lib/numra/backups
BACKUP_MAX_AGE_SECONDS=$((26 * 3600))

declare -A ENDPOINTS=(
  [prod]="http://127.0.0.1:17800/v1/health/ready"
  [audit]="http://127.0.0.1:17801/v1/health/ready"
)

failures=()
lines=()

for name in prod audit; do
  url="${ENDPOINTS[$name]}"
  body=$(curl -sf -m 10 "$url" 2>/dev/null)
  rc=$?
  if [[ $rc -ne 0 ]]; then
    failures+=("$name:readiness_unreachable")
    lines+=("\"${name}_readiness\":\"unreachable\"")
    continue
  fi
  overall=$(printf '%s' "$body" | sed -n 's/.*"status":"\([a-z]*\)".*/\1/p')
  if [[ "$overall" != "healthy" ]]; then
    failures+=("$name:readiness_${overall:-unknown}")
  fi
  lines+=("\"${name}_readiness\":\"${overall:-unknown}\",\"${name}_payload\":$(printf '%s' "$body" | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin)))' 2>/dev/null || echo '{}')")
done

newest_dump=$(ls -1t "$BACKUP_DIR"/numra-*.dump 2>/dev/null | head -1)
if [[ -z "$newest_dump" ]]; then
  failures+=("backup:no_dump_found")
  lines+=("\"backup_age_seconds\":null")
else
  age=$(( $(date +%s) - $(stat -c %Y "$newest_dump") ))
  lines+=("\"backup_age_seconds\":$age,\"backup_file\":\"$(basename "$newest_dump")\"")
  if (( age > BACKUP_MAX_AGE_SECONDS )); then
    failures+=("backup:stale_${age}s")
  fi
fi

# Job health: a growing pile of FAILED jobs is the signal a worker is not keeping up
# or a provider is misbehaving. Counted, never repaired here.
for stack in prod audit; do
  container="numra-${stack}-postgres-1"
  [ "$stack" = "prod" ] || container="numra-audit-postgres-1"
  counts=$(docker exec -i "$container" psql -U numra -d numra -t -A -c \
    "select (select count(*) from report_jobs where status='FAILED') || '/' ||
            (select count(*) from analysis_jobs where status='FAILED')" 2>/dev/null)
  if [[ -z "$counts" ]]; then
    lines+=("\"${stack}_failed_jobs\":\"unavailable\"")
  else
    lines+=("\"${stack}_failed_jobs\":\"$counts\"")
  fi
done

failure_json="[]"
if (( ${#failures[@]} > 0 )); then
  failure_json=$(printf '"%s",' "${failures[@]}"; printf '')
  failure_json="[${failure_json%,}]"
fi

{
  printf '{"checked_at":"%s",' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  ( IFS=,; printf '%s' "${lines[*]}" )
  printf ',"failures":%s}\n' "$failure_json"
} > "$STATUS_FILE" 2>/dev/null || true

if (( ${#failures[@]} > 0 )); then
  echo "NUMRA healthcheck FAILED: ${failures[*]}" >&2
  exit 1
fi
echo "NUMRA healthcheck OK"
