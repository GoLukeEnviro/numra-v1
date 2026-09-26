#!/usr/bin/env bash
# AVENYTH V2 flag probe — read-only, unauthenticated, credential-free.
#
# Every V2 router carries its flag check as a *router-level* dependency
# (services/feature_flags.py), which FastAPI runs before the route's own auth
# dependency. An anonymous request therefore answers:
#   503 {"code":"V2_DISABLED"} / {"code":"V2_PHASE_DISABLED"...}  -> flag OFF
#   401 {"code":"NOT_AUTHENTICATED"}                              -> flag ON
# No account, cookie or secret is needed, and nothing is written.
#
# Usage:
#   scripts/ops/v2-flag-probe.sh [BASE_URL] [EXPECTED]
#     BASE_URL  default https://avenyth.de/api   (host-local: http://127.0.0.1:17800)
#     EXPECTED  stage name: stage0 | stage1 | stage2 | stage3  (optional)
#               stage0 = all off; stage1 = master only (personal workspace);
#               stage2 = master + connections + relationship_workspaces;
#               stage3 = all seven on
# Exit code: 0 = matches EXPECTED (or no EXPECTED given), 1 = mismatch, 2 = probe error.
# Ref: docs/ops/2026-09-26-v2-activation-connections-workspaces.md
set -uo pipefail

BASE="${1:-https://avenyth.de/api}"
BASE="${BASE%/}"
EXPECTED="${2:-}"
NIL="00000000-0000-0000-0000-000000000000"

# flag-name | probe path (GET, anonymous)
PROBES=(
  "v2_master|/v1/me/workspace"
  "connections|/v1/connections"
  "relationship_workspaces|/v1/workspaces"
  "checkins|/v1/workspaces/${NIL}/checkins"
  "tasks|/v1/workspaces/${NIL}/tasks"
  "copilot|/v1/me/copilot/threads"
  "evidence_layer|/v1/people/${NIL}/life-tracking-entries"
)

expected_state() {  # $1 = stage, $2 = flag -> on|off
  local stage="$1" flag="$2"
  case "$stage" in
    stage0) echo off ;;
    stage1) [ "$flag" = v2_master ] && echo on || echo off ;;
    stage2) case "$flag" in v2_master|connections|relationship_workspaces) echo on ;; *) echo off ;; esac ;;
    stage3) echo on ;;
    *) echo "?" ;;
  esac
}

rc=0
printf '%-26s %-6s %-5s %s\n' "FLAG" "HTTP" "STATE" "EXPECTED"
for entry in "${PROBES[@]}"; do
  flag="${entry%%|*}"; path="${entry#*|}"
  out=$(curl -sS -m 15 -A "avenyth-v2-flag-probe" -w $'\n%{http_code}' "${BASE}${path}" 2>/dev/null) || { echo "probe error: ${BASE}${path}" >&2; exit 2; }
  code="${out##*$'\n'}"; body="${out%$'\n'*}"
  if [ "$code" = "503" ] && printf '%s' "$body" | grep -q 'V2_'; then state=off
  elif [ "$code" = "401" ]; then state=on
  else state="unexpected(${code})"; rc=2
  fi
  exp="-"
  if [ -n "$EXPECTED" ]; then
    exp=$(expected_state "$EXPECTED" "$flag")
    [ "$exp" = "?" ] && { echo "unknown stage: $EXPECTED" >&2; exit 2; }
    [ "$state" = "$exp" ] || { [ "$rc" -eq 0 ] && rc=1; }
  fi
  printf '%-26s %-6s %-5s %s\n' "$flag" "$code" "$state" "$exp"
done

ready=$(curl -sS -m 15 "${BASE}/v1/health/ready" 2>/dev/null | sed -n 's/.*"status":[[:space:]]*"\([a-z]*\)".*/\1/p' | head -1)
printf '%-26s %-6s %s\n' "readiness" "-" "${ready:-unreachable}"
[ "$ready" = "healthy" ] || rc=2

case "$rc" in
  0) echo "RESULT: OK${EXPECTED:+ (matches $EXPECTED)}" ;;
  1) echo "RESULT: MISMATCH against $EXPECTED" ;;
  *) echo "RESULT: PROBE_ERROR" ;;
esac
exit "$rc"
