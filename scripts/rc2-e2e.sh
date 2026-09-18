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
  docker exec "${PROJECT}-redis-1" sh -lc \
    'redis-cli --scan --pattern "auth:*" | while read -r k; do redis-cli del "$k" >/dev/null; done' \
    2>/dev/null || true
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
    echo "rate-limit counters cleared"
    ;;
  logs) "${COMPOSE[@]}" logs --no-color ;;
  down) "${COMPOSE[@]}" down -v --remove-orphans ;;
  *) echo "usage: $0 {up|test|audit|reset-limits|logs|down}" >&2; exit 2 ;;
esac
