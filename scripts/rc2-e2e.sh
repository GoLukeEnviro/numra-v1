#!/usr/bin/env bash
# REALITY_CHECK_2 Phase 2 -- isolated two-account Playwright journey against the
# real docker-compose topology.
#
#   scripts/rc2-e2e.sh up       # build + start the isolated stack, wait healthy
#   scripts/rc2-e2e.sh test     # run the Playwright journey (desktop + mobile)
#   scripts/rc2-e2e.sh logs     # dump compose logs
#   scripts/rc2-e2e.sh down     # tear down ONLY this project, incl. its volumes
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

case "${1:-}" in
  up)
    "${COMPOSE[@]}" build
    "${COMPOSE[@]}" up -d
    echo "waiting for api liveness/readiness + web ..."
    for i in $(seq 1 90); do curl -sf http://127.0.0.1:58000/v1/health/live >/dev/null && break; sleep 2; done
    curl -sf http://127.0.0.1:58000/v1/health/live  || { "${COMPOSE[@]}" logs; exit 1; }
    for i in $(seq 1 90); do curl -sf http://127.0.0.1:58000/v1/health/ready >/dev/null && break; sleep 2; done
    curl -sf http://127.0.0.1:58000/v1/health/ready || { "${COMPOSE[@]}" logs; exit 1; }
    for i in $(seq 1 90); do curl -sf http://127.0.0.1:3100/login >/dev/null && break; sleep 2; done
    curl -sf http://127.0.0.1:3100/login >/dev/null || { "${COMPOSE[@]}" logs; exit 1; }
    "${COMPOSE[@]}" ps --all
    ;;
  test)
    shift || true
    cd apps/web
    npx playwright test --config=playwright.rc2.config.ts "$@"
    ;;
  logs) "${COMPOSE[@]}" logs --no-color ;;
  down) "${COMPOSE[@]}" down -v --remove-orphans ;;
  *) echo "usage: $0 {up|test|logs|down}" >&2; exit 2 ;;
esac
