# Phase 2 Evidence — API + Persistence + OpenAPI + TS Client

| Item | Status |
|---|---|
| Alembic migrations (`alembic upgrade head` on empty DB) | PASS |
| Alembic downgrade → upgrade cycle | PASS |
| App boots against a freshly-migrated empty DB | PASS |
| API integration tests (real PostgreSQL 16, not mocked) | PASS — 23 passed |
| OpenAPI generation deterministic (`export_openapi.py --check`) | PASS |
| TS client generated (`openapi-typescript`) | PASS |
| DB integration tests (auth, people, calculations, relationships, cascade delete) | PASS |
| Auth tests (register/login/logout/me, wrong password, CSRF) | PASS |
| Future birth date API test | PASS |
| Engine still has zero DB imports | PASS (see below) |
| ruff format / ruff check / mypy strict | PASS |
| Coverage (`apps/api`) | 89% |

## Commands run

```text
$ sudo -u postgres psql -c "CREATE USER numra ..." / CREATE DATABASE numra_dev / numra_test
CREATE ROLE / CREATE DATABASE / CREATE DATABASE

$ cd apps/api && DATABASE_URL=postgresql+asyncpg://numra:...@127.0.0.1:5432/numra_dev \
    uv run alembic revision --autogenerate -m "initial schema"
Generating .../alembic/versions/4284dfff4331_initial_schema.py ... done

$ DATABASE_URL=.../numra_dev uv run alembic upgrade head
Running upgrade  -> 4284dfff4331, initial schema
$ psql ... -c "\dt"
12 tables (users, sessions, people, name_identities, calculations, relationships, reports,
report_sections, report_jobs, llm_generations, exports, alembic_version)

$ DATABASE_URL=.../numra_test uv run alembic upgrade head && alembic downgrade base && alembic upgrade head
(all three succeed)

$ uv run python3 -c "from numra_api.app import create_app; create_app()"  # against freshly-migrated empty DB
boot OK

$ uv run pytest apps/api/tests -q --cov=apps/api/src/numra_api --cov-report=term-missing
23 passed, 89% coverage

$ uv run ruff format --check . && uv run ruff check . && \
  uv run mypy apps/api/src packages/engine-numerology/src packages/engine-interpretation/src packages/engine-astrology/src
All checks passed! / Success: no issues found in 77 source files

$ uv run python3 scripts/export_openapi.py && uv run python3 scripts/export_openapi.py --check
Wrote openapi/numra-v1.json
OpenAPI schema up to date.

$ pnpm install && pnpm --filter @numra/schema generate
🚀 ../../openapi/numra-v1.json -> ./src/generated/schema.d.ts

$ grep -rl "sqlalchemy\|asyncpg\|fastapi" packages/engine-numerology/src
(no matches)
```

## Architecture notes

- `apps/api` is a stateless FastAPI factory (`create_app()`); the module-level `app` is the
  only global. Middleware chain: `CorrelationIdMiddleware → SecurityHeadersMiddleware →
  CORSMiddleware → AccessLogMiddleware → RequestBodyLimitMiddleware →
  OriginValidationMiddleware` (declared in that add_middleware order; Starlette runs the
  last-added middleware first on the request path, so origin validation happens before the
  request reaches routing, and CORS/security headers still wrap the response correctly).
- The Engine (`numra_numerology`) is never imported by anything under `apps/api/src`
  except at the service layer (`services/calculation_service.py`,
  `services/person_service.py`) — repositories and routes never call it directly, and the
  engine package itself imports nothing from `numra_api`, SQLAlchemy, or FastAPI (verified
  by grep above).
- `FUTURE_BIRTH_DATE_NOT_ALLOWED` is enforced in `services/person_service.py` — an
  application-layer check using `APP_TIMEZONE`, never inside the engine (canon-spec.md §30).
- Calculations are immutable snapshots (`Calculation.canonical_profile_json` +
  `deterministic_hash`, no update path in the repository layer) — a new engine run always
  creates a new row.
- Auth: Argon2id password hashes, cryptographically random session tokens (`secrets.token_urlsafe`),
  only the SHA-256 hash of the token stored in `sessions.token_hash`, `HttpOnly`/`SameSite=Lax`
  cookies, `Secure` gated on `environment=="production"`. CSRF via double-submit cookie
  (`numra_csrf` cookie + `x-csrf-token` header) enforced on all state-changing people/
  calculations/relationships routes. `ALLOW_SELF_SIGNUP` defaults to `false`; the
  `/v1/auth/register` route 403s with `SELF_SIGNUP_DISABLED` unless explicitly enabled
  (tested both ways).

## Judgment calls made explicit

- **Endpoint prefix**: used `/v1/...` (no `/api` prefix) — matches the master prompt's
  §82 endpoint list verbatim, even though `docker compose` health-check examples elsewhere
  in the wider prompt context use `/api/v1/...`; this repo's own spec (§82) is the
  authority for this project.
- **Reports/Report-Jobs/Exports endpoints are deferred to Phase 4.** The master prompt's own
  phase breakdown (§174) puts "Long-Form Report Pipeline + Worker" in Phase 4, and the
  report/report-job/export tables and job-queue semantics are meaningless without that
  pipeline; building empty CRUD stubs now would violate "no fake results" (§156).
  `/v1/account/delete-all` is likewise deferred to Phase 6 (privacy phase, §137).
- **`GET /v1/people/{id}/timing`** recomputes the engine ad-hoc and does **not** persist a
  new `Calculation` row — persisting one per "what's my personal day today" lookup would
  defeat the point of calculations being deliberate immutable snapshots. This is a
  judgment call not spelled out explicitly in the master prompt.
- **PostgreSQL, not Docker, for local dev/test in this environment**: the sandbox has no
  running Docker daemon (`docker info` fails — `EXTERNAL_DEPENDENCY_NOT_AVAILABLE`), but
  PostgreSQL 16 is installed locally, so migrations and all integration tests above ran
  against a **real** Postgres instance (`numra_dev`/`numra_test`), not SQLite and not mocks.
  Docker Compose itself (service wiring, container health checks) is verified in Phase 6
  and flagged there if Docker remains unavailable.
