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
#   * per-service readiness is judged against EXPECTED_DEPENDENCIES (see below):
#       - config deviation (required reports `disabled`, optional-disabled reports
#         anything but `disabled`)                                  -> failure, at once
#       - `degraded`, or fewer than FAIL_THRESHOLD consecutive
#         `unhealthy`/endpoint failures                              -> warning only
#       - FAIL_THRESHOLD (default 3) consecutive `unhealthy` or
#         endpoint failures (unreachable, not JSON, no `status`)     -> failure
#     The counters live in the status file, survive between timer runs and drop back to
#     0 on the first healthy check (reported once as a recovery).
#   * the job probe of a configured stack cannot read the database -> failure
#     (an unreadable pipeline is indistinguishable from a broken one)
#   * NEW failed jobs since the previous probe (per stack)         -> failure
#     The absolute number is NOT an alarm: a historical backlog from development would
#     otherwise alarm every five minutes forever.
#   * newest database dump older than 26 h                         -> failure
#   * status file cannot be written (atomically, temp + rename)     -> failure
#     (`status:file_unwritable`; without the file the counters are lost, so a quiet
#     fail-open here would disarm the threshold alarm)
#   * invalid or duplicate EXPECTED_DEPENDENCIES entries            -> failure
#     (`config:invalid_expectation_<entry>`; names match [a-z0-9_]+)
#
# Configuration: CONFIG_FILE (default /etc/numra/healthcheck.env, optional, sourced if
# readable). CONFIG_FILE, STATUS_FILE, BACKUP_DIR and BACKUP_MAX_AGE_SECONDS can be
# injected through the environment (the test harness runs entirely inside a temp dir);
# the config file may override them again. Set `AUDIT_READY_URL=` to an empty value to
# stop probing the audit instance -- that is the documented switch for the PWA-10
# teardown, so removing the stack cannot leave a permanently failed unit behind.
#   EXPECTED_DEPENDENCIES  space/comma separated `<service>=<required|optional-disabled>`
#                          for the services in the readiness body (database,
#                          numerology_engine, llm, pdf). Empty/unset: only the overall
#                          `status` is judged.
#   FAIL_THRESHOLD         consecutive failures before alarm (default 3; with the
#                          five-minute timer an outage is detected within 15 minutes).
#   STALE_QUEUED_MINUTES   (default 15, matches the V2 activation runbook's abort
#                          criterion in docs/ops/2026-09-26-v2-activation-connections-
#                          workspaces.md §7.7) how long a report/analysis job may sit in
#                          QUEUED before it counts as stuck -- the V2 job pipeline has
#                          exactly one consumer, so a growing QUEUED count almost always
#                          means that process died or the LLM provider is misconfigured.
#
# The readiness body is read for HTTP 200 and 503 alike (no `curl -f`): a 503 carries the
# very per-service detail this probe needs.
#
# Deliberately no secrets: every check reads a loopback HTTP endpoint, a directory
# listing or a database count. The stacks' env files are never read.
#
# Exit codes: 0 = no alarm (warnings may exist), 1 = at least one failure.
set -uo pipefail

STATUS_FILE=${STATUS_FILE:-/var/lib/numra/health-status.json}
BACKUP_DIR=${BACKUP_DIR:-/var/lib/numra/backups}
BACKUP_MAX_AGE_SECONDS=${BACKUP_MAX_AGE_SECONDS:-$((26 * 3600))}
CONFIG_FILE=${CONFIG_FILE:-/etc/numra/healthcheck.env}

# shellcheck disable=SC1090
[ -r "$CONFIG_FILE" ] && . "$CONFIG_FILE"

PROD_READY_URL=${PROD_READY_URL-http://127.0.0.1:17800/v1/health/ready}
PROD_DB_CONTAINER=${PROD_DB_CONTAINER-numra-prod-postgres-1}
AUDIT_READY_URL=${AUDIT_READY_URL-http://127.0.0.1:17801/v1/health/ready}
AUDIT_DB_CONTAINER=${AUDIT_DB_CONTAINER-numra-audit-postgres-1}
STALE_QUEUED_MINUTES=${STALE_QUEUED_MINUTES-15}
EXPECTED_DEPENDENCIES=${EXPECTED_DEPENDENCIES-}
FAIL_THRESHOLD=${FAIL_THRESHOLD-3}
case "$FAIL_THRESHOLD" in '' | *[!0-9]* | 0) FAIL_THRESHOLD=3 ;; esac

failures=()
warnings=()
recoveries=()
lines=()
dep_names=()
declare -A dep_class=()
declare -A prev=()

# --- helpers -------------------------------------------------------------------------

json_string() { printf '"%s"' "$(printf '%s' "$1" | tr -d '\000-\037' | sed 's/\\/\\\\/g; s/"/\\"/g')"; }

json_array() {
  local item out=""
  for item in "$@"; do out+="$(json_string "$item"),"; done
  printf '[%s]' "${out%,}"
}

# Integer values of the previous status file, as `prev[key]` (counters, failed totals).
load_previous() {
  local key value
  while read -r key value; do
    prev[$key]=$value
  done < <(python3 - "$STATUS_FILE" <<'PY' 2>/dev/null
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        for key, value in json.load(handle).items():
            if isinstance(value, int) and not isinstance(value, bool):
                print(key, value)
except Exception:
    pass
PY
)
}

parse_expectations() {
  local entry name class entries
  set -f # entries are data, never globs
  # shellcheck disable=SC2206
  entries=(${EXPECTED_DEPENDENCIES//,/ })
  set +f
  for entry in "${entries[@]}"; do
    name=${entry%%=*}
    class=${entry#*=}
    case "$class" in
      required | optional-disabled) ;;
      *) failures+=("config:invalid_expectation_${entry}"); continue ;;
    esac
    case "$name" in '' | *[!a-z0-9_]*) failures+=("config:invalid_expectation_${entry}"); continue ;; esac
    if [ -n "${dep_class[$name]+set}" ]; then
      failures+=("config:invalid_expectation_duplicate_${entry}")
      continue
    fi
    dep_names+=("$name")
    dep_class[$name]=$class
  done
}

# Per-service counters live in the status file as `<stack>_fail_count_<label>`.
counter_key() { printf '%s_fail_count_%s' "$1" "$2"; }

keep_counter() {
  local key; key=$(counter_key "$1" "$2")
  lines+=("\"$key\":${prev[$key]:-0}")
}

record_ok() {
  local key; key=$(counter_key "$1" "$2")
  lines+=("\"$key\":0")
  [ "${prev[$key]:-0}" -gt 0 ] && recoveries+=("$1:${2}_recovered")
  return 0
}

# record_failure <stack> <label> <detail> [extra]
record_failure() {
  local key n
  key=$(counter_key "$1" "$2")
  n=$(( ${prev[$key]:-0} + 1 ))
  lines+=("\"$key\":$n")
  if [ "$n" -ge "$FAIL_THRESHOLD" ]; then
    failures+=("$1:${2}_${3}_${n}x${4:-}")
  else
    warnings+=("$1:${2}_${3}_${n}_of_${FAIL_THRESHOLD}${4:-}")
  fi
}

endpoint_failure() {
  local name="$1" cause="$2" dep
  lines+=("\"${name}_readiness\":\"${cause}\"")
  record_failure "$name" readiness failed "($cause)"
  for dep in "${dep_names[@]}"; do keep_counter "$name" "$dep"; done
}

# Judge one service value against its expectation. Returns 0 when the value explains an
# unhealthy overall status (degraded/unhealthy), 1 otherwise.
judge_dependency() {
  local name="$1" dep="$2" value="$3" class="${dep_class[$2]}"
  lines+=("\"${name}_${dep}\":\"${value}\"")
  if [ "$class" = "optional-disabled" ]; then
    if [ "$value" = "disabled" ]; then record_ok "$name" "$dep"; return 1; fi
    failures+=("$name:config_deviation:${dep}_optional-disabled_but_${value}")
    keep_counter "$name" "$dep"
    return 1
  fi
  case "$value" in
    healthy) record_ok "$name" "$dep"; return 1 ;;
    disabled)
      failures+=("$name:config_deviation:${dep}_required_but_disabled")
      keep_counter "$name" "$dep"; return 1 ;;
    degraded)
      warnings+=("$name:${dep}_degraded")
      keep_counter "$name" "$dep"; return 0 ;;
    *) record_failure "$name" "$dep" "$value"; return 0 ;;
  esac
}

probe_readiness() {
  local name="$1" url="$2" raw rc code body parsed overall dep value explained=1 line
  if [ -z "$url" ]; then
    lines+=("\"${name}_readiness\":\"not_configured\"")
    return 0
  fi
  raw=$(curl -s -m 10 -w '\n%{http_code}' "$url" 2>/dev/null)
  rc=$?
  if [ "$rc" -ne 0 ]; then endpoint_failure "$name" unreachable; return 0; fi
  code=${raw##*$'\n'}
  body=${raw%$'\n'*}
  case "$code" in
    200 | 503) ;;
    *) endpoint_failure "$name" "http_${code}"; return 0 ;;
  esac
  parsed=$(printf '%s' "$body" | python3 -c '
import json, re, sys
try:
    data = json.load(sys.stdin)
    status = data["status"]
    assert isinstance(data, dict) and isinstance(status, str)
except Exception:
    sys.exit(1)
def clean(value):
    return re.sub(r"[^a-z_-]", "", value.lower()) if isinstance(value, str) else "missing"
print("status=" + (clean(status) or "unknown"))
for name in sys.argv[1:]:
    print("dep.%s=%s" % (name, clean(data.get(name)) or "unknown"))
' "${dep_names[@]}" 2>/dev/null) || { endpoint_failure "$name" invalid_json; return 0; }

  overall=$(printf '%s\n' "$parsed" | sed -n 's/^status=//p')
  lines+=("\"${name}_readiness\":\"${overall}\"")
  for dep in "${dep_names[@]}"; do
    value=$(printf '%s\n' "$parsed" | sed -n "s/^dep\.${dep}=//p")
    judge_dependency "$name" "$dep" "${value:-missing}"
    [ "$?" -eq 0 ] && explained=0
  done

  case "$overall" in
    healthy) record_ok "$name" readiness ;;
    degraded) warnings+=("$name:readiness_degraded"); keep_counter "$name" readiness ;;
    *)
      if [ "$explained" -eq 0 ]; then
        keep_counter "$name" readiness
      else
        record_failure "$name" readiness failed "(status_${overall})"
      fi ;;
  esac
}

# Job health. `previous` is the same stack's FAILED total from the last probe (-1 when
# unknown). Returns "" and records a failure when the database cannot be read. The 24h
# window counts report AND analysis failures.
probe_jobs() {
  local name="$1" container="$2" previous="$3" counts total window stale delta
  counts=$(docker exec -i "$container" psql -U numra -d numra -t -A -c \
    "select (select count(*) from report_jobs where status='FAILED') || ' ' ||
            (select count(*) from analysis_jobs where status='FAILED') || ' ' ||
            ((select count(*) from report_jobs where status='FAILED'
                and updated_at > now() - interval '24 hours') +
             (select count(*) from analysis_jobs where status='FAILED'
                and updated_at > now() - interval '24 hours')) || ' ' ||
            ((select count(*) from report_jobs where status='QUEUED'
               and created_at < now() - interval '${STALE_QUEUED_MINUTES} minutes') +
             (select count(*) from analysis_jobs where status='QUEUED'
               and created_at < now() - interval '${STALE_QUEUED_MINUTES} minutes'))" 2>/dev/null)
  if [ -z "$counts" ]; then
    failures+=("$name:jobs_unreadable")
    lines+=("\"${name}_failed_jobs\":null,\"${name}_failed_jobs_24h\":null,\"${name}_stale_queued\":null")
    return 0
  fi
  total=$(printf '%s' "$counts" | awk '{print $1+$2}')
  window=$(printf '%s' "$counts" | awk '{print $3}')
  stale=$(printf '%s' "$counts" | awk '{print $4}')
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
  if [ "$stale" -gt 0 ] 2>/dev/null; then
    failures+=("$name:${stale}_stale_queued_job(s)_over_${STALE_QUEUED_MINUTES}m")
  fi
  lines+=("\"${name}_failed_jobs\":$total,\"${name}_failed_jobs_24h\":$window,\"${name}_new_failed_jobs\":\"$delta\",\"${name}_stale_queued\":$stale")
}

# --- checks --------------------------------------------------------------------------

load_previous
parse_expectations

probe_readiness prod "$PROD_READY_URL"
probe_jobs prod "$PROD_DB_CONTAINER" "${prev[prod_failed_jobs]:--1}"

probe_readiness audit "$AUDIT_READY_URL"
if [ -n "$AUDIT_READY_URL" ]; then
  probe_jobs audit "$AUDIT_DB_CONTAINER" "${prev[audit_failed_jobs]:--1}"
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

# Atomic write (temp file in the same directory + rename). A status file that cannot be
# written is itself a failure: without it the persisted counters are lost and a
# threshold alarm could never fire (fail-closed).
status_tmp=""
trap '[ -z "$status_tmp" ] || rm -f "$status_tmp"' EXIT
write_status() {
  status_tmp=$(mktemp "$(dirname "$STATUS_FILE")/.health-status.XXXXXX" 2>/dev/null) || return 1
  {
    printf '{"checked_at":"%s",' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    ( IFS=,; printf '%s' "${lines[*]}" )
    printf ',"failures":%s,"warnings":%s,"recoveries":%s}\n' \
      "$(json_array "${failures[@]}")" "$(json_array "${warnings[@]}")" "$(json_array "${recoveries[@]}")"
  } > "$status_tmp" 2>/dev/null &&
    chmod 0644 "$status_tmp" 2>/dev/null &&
    mv -T "$status_tmp" "$STATUS_FILE" 2>/dev/null &&
    status_tmp=""
}
write_status || failures+=("status:file_unwritable")

[ "${#warnings[@]}" -eq 0 ] || echo "NUMRA healthcheck WARN: ${warnings[*]}"
[ "${#recoveries[@]}" -eq 0 ] || echo "NUMRA healthcheck RECOVERED: ${recoveries[*]}"

if [ "${#failures[@]}" -gt 0 ]; then
  echo "NUMRA healthcheck FAILED: ${failures[*]}" >&2
  exit 1
fi
echo "NUMRA healthcheck OK"
