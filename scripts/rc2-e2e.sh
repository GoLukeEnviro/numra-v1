#!/usr/bin/env bash
# REALITY_CHECK_2 Phase 2 -- isolated two-account Playwright journey against the
# real docker-compose topology.
#
#   scripts/rc2-e2e.sh up            # build + start the isolated stack, wait healthy
#   scripts/rc2-e2e.sh test          # run the Playwright journey (desktop + mobile)
#   scripts/rc2-e2e.sh audit         # up + reset-limits + test + down -- one automated pass
#   scripts/rc2-e2e.sh reset-limits  # clear the API's per-IP rate-limit counters
#   scripts/rc2-e2e.sh logs          # dump compose logs
#   scripts/rc2-e2e.sh down          # tear down ONLY this project, incl. its volumes
#
# All values below are throwaway test credentials for a local, isolated stack.
set -euo pipefail

PROJECT=numra-rc2
COMPOSE=(docker compose -p "$PROJECT" -f docker-compose.yml -f docker-compose.rc2.yml)

export POSTGRES_PASSWORD=rc2-only-postgres-password
export SESSION_SECRET=rc2-only-session-secret-0123456789-abcdefghij
export PDF_INTERNAL_TOKEN=rc2-only-pdf-token
export ENVIRONMENT=test
export ALLOW_SELF_SIGNUP=true
export NUMRA_LLM_PROVIDER=mock
# This script always starts its stack with the deterministic mock provider (line
# above), so the journey may and must assert the mock's fixed Copilot reply -- a
# stronger guard than "some answer appeared". An acceptance run against a stack with
# a REAL provider must NOT set this (see the spec's RC2_EXPECT_MOCK).
export RC2_EXPECT_MOCK=1
export RATE_LIMIT_BACKEND=redis
export COMPOSE_WEB_PORT=3100

cd "$(dirname "$0")/.."

reset_limits() {
  # The register endpoint is limited to 5/hour per client IP, and the journey
  # registers two accounts per viewport project. Through the Next.js proxy the
  # API sees the web container's IP for every run, so the counter is shared
  # across runs and a second pass within the hour would fail with
  # RATE_LIMIT_EXCEEDED. The counter is throwaway state of this throwaway
  # stack -- clear it so every run starts from a known state.
  #
  # This must never fail silently: a no-op reset is indistinguishable from a
  # successful one until the run dies several minutes later with
  # RATE_LIMIT_EXCEEDED, which is exactly the failure this helper exists to
  # prevent. So the redis call's own exit status decides: unreachable redis is a
  # hard error in the deterministic up/audit paths (set -e propagates it), while
  # "no matching keys" is a normal, reported outcome.
  #
  # Addressed by compose service (not a hardcoded container name) so a project
  # rename cannot silently turn this into a no-op.
  local deleted
  if ! deleted=$("${COMPOSE[@]}" exec -T redis \
    sh -lc 'n=0; for k in $(redis-cli --scan --pattern "auth:*"); do redis-cli del "$k" >/dev/null; n=$((n+1)); done; echo "$n"'); then
    echo "reset-limits: FAILED -- could not reach the stack's redis; the register" >&2
    echo "rate-limit counters were NOT cleared. Fix the stack before running the suite." >&2
    return 1
  fi
  deleted=$(printf '%s' "$deleted" | tr -d '\r\n')
  if [ "${deleted:-0}" = "0" ]; then
    echo "reset-limits: no auth:* counters present (clean state)"
  else
    echo "reset-limits: cleared ${deleted} auth:* counter(s)"
  fi
  # Never touch other namespaces: admin:* and friends are not rate-limit state.
}

wait_healthy() {
  echo "waiting for api liveness/readiness + web ..."
  for i in $(seq 1 90); do curl -sf http://127.0.0.1:58080/v1/health/live >/dev/null && break; sleep 2; done
  curl -sf http://127.0.0.1:58080/v1/health/live  || { "${COMPOSE[@]}" logs; exit 1; }
  for i in $(seq 1 90); do curl -sf http://127.0.0.1:58080/v1/health/ready >/dev/null && break; sleep 2; done
  curl -sf http://127.0.0.1:58080/v1/health/ready || { "${COMPOSE[@]}" logs; exit 1; }
  for i in $(seq 1 90); do curl -sf http://127.0.0.1:3100/login >/dev/null && break; sleep 2; done
  curl -sf http://127.0.0.1:3100/login >/dev/null || { "${COMPOSE[@]}" logs; exit 1; }
  "${COMPOSE[@]}" ps --all
}

case "${1:-}" in
  up)
    "${COMPOSE[@]}" build
    "${COMPOSE[@]}" up -d
    wait_healthy
    reset_limits
    ;;
  test)
    shift || true
    cd apps/web
    npx playwright test --config=playwright.rc2.config.ts "$@"
    ;;
  audit)
    shift || true
    "${COMPOSE[@]}" build
    "${COMPOSE[@]}" up -d
    wait_healthy
    reset_limits
    rc=0
    (cd apps/web && npx playwright test --config=playwright.rc2.config.ts "$@") || rc=$?
    echo "--- collected screenshots/logs (test-results/rc2) ---"
    ls -R apps/web/test-results/rc2 2>/dev/null || true
    "${COMPOSE[@]}" down -v --remove-orphans
    exit "$rc"
    ;;
  reset-limits)
    reset_limits
    ;;
  logs) "${COMPOSE[@]}" logs --no-color ;;
  down) "${COMPOSE[@]}" down -v --remove-orphans ;;
  *) echo "usage: $0 {up|test|audit|reset-limits|logs|down}" >&2; exit 2 ;;
esac
