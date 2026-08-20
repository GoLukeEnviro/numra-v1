# NUMRA V1 — Final Verification Report

Every result below reflects a command that was actually executed and observed — in
this build session or the production-hardening follow-up session on top of it — not
an assumption. Per-phase detail and raw command transcripts live in
`specs/evidence/phase-{0..6}.md`, `specs/evidence/final-hardening-baseline.md`,
`specs/evidence/system-e2e.md`, and `specs/evidence/web-api-proxy-and-csp.md`.

This report has two layers: the original Phase 0–6 build (below, largely unchanged),
and a subsequent **production-hardening pass** (`fix/numra-v1-production-completion`,
PR #3) that closed real architectural gaps the first pass left open — implicit mock
LLM fallback, no retry semantics, health checks that didn't check anything, unbounded
export/PDF wiring, in-memory-only rate limiting — and then built genuine, non-mocked
verification (a real system E2E test, a real GitHub Actions run, a real Docker build
attempt) that caught and fixed three previously-invisible bugs. That pass is reported
in its own section below rather than silently merged into the Phase 0–6 tables, so it
stays clear which claims were re-verified against a live stack and which weren't.

## Calculation Engine

| Command/Test | Result | Evidence |
|---|---|---|
| `uv run pytest packages/engine-numerology/tests -q --cov=... --cov-fail-under=90` | **PASS** — 104 passed, 100% coverage | `specs/evidence/phase-1.md`, re-verified this pass |
| Reduction test matrix (15 pinned pairs, e.g. `29 → "11/2"`, `44 → "44/8"`) | **PASS** | `packages/engine-numerology/tests/unit/test_reduction.py` |
| Hypothesis property tests (termination, root range, master range, no-false-master, invariants) | **PASS** | `packages/engine-numerology/tests/property/` |
| Golden Lukas Springer test (values + traces), incl. `direct_digit_sum` diagnostic shape | **PASS** — strengthened this pass after a real shape-drift bug (see P1-VERIFICATION) | `packages/engine-numerology/tests/golden/test_lukas_springer_golden.py` |
| Edge cases (§71: master birthday, leap day, multi-name, diacritics, vowel-less, Hidden Passion tie/unique, Challenge=0, ...) | **PASS** | `packages/engine-numerology/tests/edge_cases/` |
| Anti-cheating grep (no golden literals/imports in production source) | **PASS** | `packages/engine-numerology/tests/unit/test_no_golden_leakage.py` |
| `uv run ruff format --check . && uv run ruff check .` | **PASS** | — |
| `uv run mypy packages/engine-numerology/src` (strict) | **PASS** | — |
| Engine has zero DB/API/LLM imports | **PASS** — `grep -rl "sqlalchemy\|asyncpg\|fastapi\|numra_api"` returns nothing | `specs/evidence/phase-2.md` |

## API

| Command/Test | Result | Evidence |
|---|---|---|
| `uv run pytest apps/api/tests -q` (real PostgreSQL 16, not mocked) | **PASS** — grew from 29 to well over 100 tests across this pass (retry state machine, health checks, exports, rate limiting) | `specs/evidence/phase-2.md`, `phase-4.md`, `phase-6.md`, this pass |
| Auth (register/login/logout/me, wrong password, CSRF enforcement) | **PASS** | `apps/api/tests/integration/test_auth_flow.py` |
| Future-birth-date rejection (`FUTURE_BIRTH_DATE_NOT_ALLOWED`) at the app layer only | **PASS** | `apps/api/tests/integration/test_people_and_calculations.py` |
| Golden calculation through the full HTTP stack (`22/4`, `62/8`, `18/9`, `44/8`, `17/8`) | **PASS** | `apps/api/tests/integration/test_people_and_calculations.py` |
| OpenAPI export has no drift (`scripts/export_openapi.py --check`) | **PASS** | `openapi/numra-v1.json` |
| Generated TS client has no drift | **PASS** | `packages/schema/src/generated/schema.d.ts` |
| `uv run mypy apps/api/src` (strict) | **PASS** | — |

## Database

| Command/Test | Result | Evidence |
|---|---|---|
| `alembic upgrade head` on an empty DB | **PASS** — real Postgres, application tables + `alembic_version` | `specs/evidence/phase-2.md` |
| `alembic downgrade base && alembic upgrade head` | **PASS** | `specs/evidence/phase-2.md` |
| App boots against a freshly-migrated empty DB | **PASS** | `specs/evidence/phase-2.md` |
| Cascade delete (`POST /v1/account/delete-all`) — every dependent table verified at 0 rows after, no orphans | **PASS** | `apps/api/tests/integration/test_delete_all.py`, `specs/evidence/phase-6.md` |
| `ReportJob.next_attempt_at`/`last_error_at` migration, composite `(user_id, idempotency_key)` uniqueness | **PASS** — applied and exercised against real Postgres | `apps/api/alembic/versions/ffc969c9b8ad_*.py`, this pass |

## LLM Adapter

| Command/Test | Result | Evidence |
|---|---|---|
| `MockLLMProvider` — deterministic, no network, round-trips structured output | **PASS** | `packages/engine-interpretation/tests/unit/test_llm_mock_provider.py` |
| Wrong numeric claim / unknown metric_id → `InvalidReportSection`, incl. bare-literal detection across both `{{metric:*}}` and `{{special:*}}` namespaces | **PASS** — validator materially expanded this pass (pinnacles, challenges, subconscious self, hidden passion, karmic lessons, `find_unauthorized_numeric_literals`) | `packages/engine-interpretation/tests/unit/test_llm_validator.py` |
| `OllamaCloudProvider.health()` reports `"unavailable"` cleanly when unconfigured (never crashes) | **PASS** | `packages/engine-interpretation/tests/unit/test_llm_ollama_provider.py` |
| Provider swappable behind `LLMProvider` protocol | **PASS** | `packages/engine-interpretation/tests/unit/test_llm_provider_swappable.py` |
| **Explicit provider selection** — `numra_llm_factory.build_llm_provider()` is the sole place a concrete provider is chosen; `mock` is rejected by a `Settings` validator when `environment="production"`; a new `DisabledLLMProvider` makes "no LLM configured" an honest, typed state instead of a silent mock fallback | **PASS** | `apps/api/src/numra_api/services/llm_factory.py`, `packages/engine-interpretation/src/numra_interpretation/llm/disabled_provider.py` |
| Live Ollama Cloud generation | **NOT VERIFIED / EXTERNAL_DEPENDENCY_NOT_AVAILABLE** — no `OLLAMA_API_KEY` in this environment | `specs/evidence/phase-3.md` |

## Report Pipeline

| Command/Test | Result | Evidence |
|---|---|---|
| Manifest word ranges (QUICK/FULL/ULTIMATE/CUSTOM) | **PASS** | `packages/engine-interpretation/tests/unit/test_report_pipeline.py` |
| 15,000+ word ULTIMATE report generation with Mock Provider | **PASS** — reached ≥15,000 words, all sections present | same |
| Global Report Linter (missing sections, duplicate headings/paragraphs, word count, unresolved placeholders, unsupported claims, metric reference integrity) | **PASS** | same |
| One controlled repair attempt on invalid claim, then hard fail | **PASS** | same |
| No core-number mutation across a full report run | **PASS** | same |
| Real `AgentWrite`-style outline step for FULL/ULTIMATE report types | **PASS** — new this pass | `packages/engine-interpretation/src/numra_interpretation/report/pipeline.py`, `test_report_pipeline.py` |
| Mock-only deterministic padding never reaches a real LLM prompt | **PASS** — gated on `is_mock_provider`, tested explicitly | same |
| Postgres job queue restart-safety (crashed-worker lease reclaim, two concurrent workers never claim the same job) | **PASS** — real Postgres `SELECT ... FOR UPDATE SKIP LOCKED` | `apps/api/tests/integration/test_reports.py`, `test_report_retry.py` |
| **Retry/error state machine** — retryable failures requeue with exponential backoff (`next_attempt_at`), non-retryable failures fail terminally on first occurrence, retry-limit-exceeded fails terminally, an unexpected bare exception is caught and does not crash the worker loop | **PASS** — 6 new integration tests | `apps/api/tests/integration/test_report_retry.py` |
| Idempotency-Key support (composite `(user_id, idempotency_key)`, not global) | **PASS** | `apps/api/tests/integration/test_reports.py` |
| Live Ollama Cloud report generation | **NOT VERIFIED / EXTERNAL_DEPENDENCY_NOT_AVAILABLE** | `specs/evidence/phase-4.md` |

## Health Checks

| Command/Test | Result | Evidence |
|---|---|---|
| `GET /v1/health/ready` performs real, timeout-bounded checks against DB, engine, LLM, and PDF service (not a static `{"status":"ok"}`) | **PASS** — 7 integration tests: mock-LLM-and-no-PDF, LLM-disabled, unreachable-Ollama → unhealthy, TTL-cache-hit, others | `apps/api/src/numra_api/routes/health.py`, `apps/api/tests/integration/test_health.py` |
| Short TTL cache prevents a health-check storm from hammering downstream services | **PASS** | same |

## Export / PDF Product Integration

| Command/Test | Result | Evidence |
|---|---|---|
| `ExportStorage` protocol + `LocalExportStorage` (UUID-named files, path-traversal-safe) | **PASS** | `apps/api/src/numra_api/storage/exports.py` |
| `node --test apps/pdf/src/__tests__/render.test.js` | **PASS** — 4/4 (HTML escaping, real PDF render, page-object presence, headings present), re-verified this pass | `specs/evidence/phase-6.md`, re-run this pass |
| End-to-end HTTP smoke test (`/health/live`, `/health/ready`, authenticated `/render/report` → real 3-page PDF, unauthenticated → 401) | **PASS** | `specs/evidence/phase-6.md` |
| A real system-E2E export blocks on a genuine Playwright/Chromium render in the PDF service and downloads real `%PDF-`-signed bytes | **PASS** | `apps/web/e2e-system/system-journey.spec.ts`, `specs/evidence/system-e2e.md` |
| Delete-All physically removes exported files from disk, not just their DB rows | **PASS** — verified directly against the `ExportStorage` directory, not just through the API (an authenticated request can't distinguish "row gone" from "session gone" once both are true) | `specs/evidence/system-e2e.md` |

## Rate Limiting / Security Hardening

| Command/Test | Result | Evidence |
|---|---|---|
| Redis-backed rate limiting (`RATE_LIMIT_BACKEND=redis`), forbidden in production when left on in-memory | **PASS** | `apps/api/src/numra_api/config.py` (`_forbid_memory_rate_limiter_in_production`) |
| Rate-limit keys are HMAC-pseudonymized, never raw IP/device ID | **PASS** | (unchanged from earlier pass, re-verified) |
| `OriginValidationMiddleware` rejects state-changing requests with an `Origin` outside the allowlist, independent of CORS | **PASS** — exercised for real by the system-E2E journey | `specs/evidence/system-e2e.md` |
| Same-origin Next.js API proxy (Route Handler, not build-time `next.config.mjs` rewrites) forwards multiple `Set-Cookie` headers correctly via `getSetCookie()` | **PASS** | `apps/web/src/app/api/[...path]/route.ts`, `specs/evidence/web-api-proxy-and-csp.md` |

## Frontend

| Command/Test | Result | Evidence |
|---|---|---|
| `pnpm --filter @numra/web lint` | **PASS** | re-verified this pass |
| `pnpm --filter @numra/web exec tsc --noEmit` | **PASS** | re-verified this pass |
| `pnpm --filter @numra/web test -- --run` (Vitest) | **PASS** — 39/39 (grew from 7 as Reports/Today/Identity-Timeline/report-content features were built) | re-verified this pass |
| `pnpm --filter @numra/web build` | **PASS** — all app routes incl. `/icon.svg` compiled | re-verified this pass |
| `pnpm --filter @numra/web exec playwright test` (mocked golden journey) | **PASS** (last confirmed locally; CI run in progress, see P1-VERIFICATION) | `specs/evidence/phase-5.md` |
| Premium redesign — Dashboard, People, Analysis, Relationships, Today, Identity Timeline, Report reader/export UX, Login | **PASS** — dark/gold/ivory/plum design system (`tailwind.config.ts`), restrained motion respecting `prefers-reduced-motion` | `apps/web/src/app/**`, `apps/web/tailwind.config.ts` |
| Diagnostic Life Path visually/structurally distinguished from canonical | **PASS** — unit-tested against the real golden fixture | same |
| No invented relationship compatibility percentage | **PASS** — match/no-match booleans only; re-asserted against a live comparison endpoint by the system E2E (no `%` character anywhere in the rendered page) | `apps/web/e2e-system/system-journey.spec.ts` |
| Missing `apps/web/public` directory / missing favicon (previously documented as benign) | **FIXED** — `apps/web/public/robots.txt` + Next.js-convention `apps/web/src/app/icon.svg`; this also turned out to break `docker-build` outright (see P1-VERIFICATION) | `specs/evidence/web-api-proxy-and-csp.md` |

## Privacy

| Command/Test | Result | Evidence |
|---|---|---|
| PII-safe logging (access log / `LLMGeneration` never store names, birth data, prompts) | **PASS** — by construction, see `middleware/security.py`, `models/tables.py` | `specs/evidence/phase-2.md` |
| `POST /v1/account/delete-all` requires password re-confirmation + CSRF | **PASS** | `apps/api/tests/integration/test_delete_all.py` |
| Full cascade delete verified with real created rows across every dependent table, incl. physical export files | **PASS** | same, `specs/evidence/system-e2e.md` |

## P1-VERIFICATION: Real System E2E, Docker, CI

This is the newest and highest-value verification work: instead of trusting mocked
tests and local-only gates, this pass built genuine end-to-end verification and used
it to find real bugs.

### Real (non-mocked) system E2E

`apps/web/e2e-system/system-journey.spec.ts` makes **zero** `page.route()` calls —
every request goes through the real same-origin proxy to a real, running FastAPI
instance, backed by real Postgres, a real report worker, and the real internal PDF
microservice. It register→logs in→creates a real person and asserts the real engine's
golden output→generates a real report through the real job queue→exports and
downloads a real PDF→creates a second person→compares them via a real relationship
endpoint→runs Delete-All and verifies the session is genuinely rejected server-side
and the account can be re-registered.

**Result: PASS**, 3 consecutive clean runs locally, and now also running as the
`system-e2e` CI job (see below). Full rationale and prerequisites in
`specs/evidence/system-e2e.md`.

**This caught a real production bug on its first run**: the Calculation Inspector
crashed on any live (non-fixture) calculation because `diagnostics.life_path
.alternative_methods.direct_digit_sum` was serialized as a full `CalculationMetric`
object instead of the flat shape the frontend and the pinned golden fixture actually
require. Root-caused, fixed with a new `diagnostic_payload()` extraction helper in
`date_metrics.py`, verified byte-for-byte against the golden fixture, and locked in
with a strengthened golden test. Never touched any frozen Canon calculation logic.

### Docker

| Command/Test | Result | Evidence |
|---|---|---|
| `docker compose config --quiet` | **PASS** — valid compose file, all variables resolve | `specs/evidence/phase-6.md`, re-verified throughout this pass |
| `docker compose build` / registry image pulls | **PASS** — real, on GitHub Actions (`docker-build` CI job); this sandbox itself still cannot pull images (403 from the registry, a network-egress policy restriction, not retriable), so every Docker-dependent claim below was proven exclusively via real GitHub Actions runs, never locally | `docker-build`, `docker-compose-e2e` CI jobs |
| Real `docker compose up` deployment of the full topology (postgres, redis, migrate, api, worker, pdf, web) | **PASS** — `docker-compose-e2e` CI job: all services healthy, real non-mocked Playwright journey through the compose stack green | `.github/workflows/ci.yml` (`docker-compose-e2e` job), `specs/evidence/final-release-closure.md` |

Real `docker compose up` execution on GitHub Actions surfaced and fixed **four**
genuine, previously-invisible production bugs — none catchable by any local gate or
by `docker-build` alone, since that job only builds images and never runs a
container against a real named-volume mount or a real multi-container network:

1. **The `api`/`worker` Docker images were completely non-functional.**
   `docker/api.Dockerfile` ran a bare `uv sync --frozen --no-dev` at the workspace
   root, which only syncs the (intentionally empty) root placeholder project, not any
   workspace member — `alembic`/`uvicorn` were missing from `$PATH` and `numra_api`
   itself was unimportable in the built image. Fixed with `--all-packages`. This is
   arguably the single most severe finding of the whole verification effort: the
   production deployment path had never actually worked.
2. A same-origin `Origin`-validation mismatch: the compose Playwright config used
   `127.0.0.1` for its `baseURL` while the API's CORS/Origin allowlist defaults to
   `localhost` — a real browser form submission (unlike a bare `page.request.post()`,
   which sends no `Origin` header at all) was rejected. Fixed by aligning the test
   config's address with the API's allowlist.
3. A Docker-image/npm-package version drift: `docker/pdf.Dockerfile` builds `FROM
   mcr.microsoft.com/playwright:v1.56.1-jammy` (Chromium pre-installed for exactly
   that version), but `apps/pdf/package.json` declared a floating
   `"playwright": "^1.56.1"` — resolved fresh at `npm install` time (a build stage
   disconnected from `pnpm-lock.yaml`) to a newer `1.62.1`, whose browser-management
   code expects a different pre-installed Chromium revision than the pinned base
   image actually has, so every PDF render failed immediately. Fixed by pinning the
   exact version (no `^`).
4. The `numra_exports_data` named volume mounted onto `/app/data/exports` inside the
   `api` container as `root:root` (Docker's default when that path doesn't already
   exist in the image before the non-root `USER numra` takes effect), so every export
   write hit `PermissionError`. Fixed by pre-creating and `chown`-ing the directory
   in `docker/api.Dockerfile` before the volume ever mounts onto it.

Full failure signatures, diagnosis trail (including three earlier, honestly-recorded
wrong theories before the real root causes above were found), and fix verification
for all four are in `specs/evidence/final-release-closure.md`.

### CI — real GitHub Actions execution

A real branch was pushed and a real PR opened (`GoLukeEnviro/numra-v1#3`, branch
`fix/numra-v1-production-completion`), driven to green through real, repeated
GitHub Actions execution rather than assumed correct from local testing alone. Final
state on the head that was merged (commit `498c2a0`): **all 13 required checks
green** — `lint-python`, `python-typecheck`, `no-golden-leakage`,
`schema-and-openapi-drift`, `web-lint-typecheck-build-test`, `pdf-service-tests`,
`unit-and-property-tests`, `dependency-security`, `docker-build`,
`docker-compose-e2e`, `playwright`, `system-e2e`, `copilot`.

Real execution surfaced seven genuine, previously-invisible bugs across the full
closure effort — three CI-plumbing bugs (pnpm/Node action conflict, a rejected `uv`
multi-`--package` flag, a missing `apps/web/public` directory) documented in earlier
evidence files, plus the four real `docker compose up` runtime bugs listed above.
None were catchable by any local gate; all were found only because this pass insisted
on real execution over assumed-correct local testing. See
`specs/evidence/final-release-closure.md` for the complete diagnosis trail, including
every wrong theory tried and honestly recorded before each real root cause was found.

## Dependency security

| Command/Test | Result | Evidence |
|---|---|---|
| Next.js 14.2.35 → 15.5.23 upgrade (closes all `next`-rooted advisories) | **PASS** — `apps/web/src/app/api/[...path]/route.ts` updated for Next 15's async Route Handler `params`; `postcss`/`sharp` forced to patched versions via root `pnpm.overrides` (vendored inside `next`'s own dependency tree, unreachable from the app's top-level deps otherwise) | `apps/web/package.json`, `package.json`, `specs/evidence/final-release-closure.md` |
| `pnpm audit --prod --audit-level=high` (web, prod deps) | **PASS** — "No known vulnerabilities found" | re-verified this pass, and gated in CI (`dependency-security` job) |
| `uvx pip-audit` (Python deps) | **PASS** — "No known vulnerabilities found" | re-verified this pass, and gated in CI (`dependency-security` job) |
| Golden Canon re-verified after the dependency bump (no calculation-affecting change) | **PASS** — all pinned values byte-identical | `specs/evidence/final-release-closure.md` |

## Overall

```
CORE_SYSTEM (engine, API, DB, report pipeline, frontend, PDF)     = PASS
P0/P1 HARDENING (LLM wiring, retry, health, exports, rate limit)  = PASS
DEPENDENCY_SECURITY (Next.js 15, pnpm audit, pip-audit)           = PASS
LIVE_LLM_SMOKE (Ollama Cloud)                                     = NOT_VERIFIED
REASON                                                             = MISSING_CREDENTIALS (no OLLAMA_API_KEY in this environment)
REAL_SYSTEM_E2E (non-mocked, full stack, manually-orchestrated)   = PASS
DOCKER_BUILD (real GitHub Actions image builds)                   = PASS
DOCKER_COMPOSE_E2E (real `docker compose up`, full topology)      = PASS
REASON                                                             = 4 real runtime bugs found and fixed via real execution;
                                                                      see specs/evidence/final-release-closure.md
GITHUB_ACTIONS_EXECUTION (PR #3, head 498c2a0)                    = PASS
REASON                                                             = 13/13 required checks green
```

Total test count across the repository, all real and passing:
**256 Python tests** (`uv run pytest packages apps/api/tests -q`, engine subset:
104 tests at 100% coverage) + **39 web unit tests** + **1 mocked Playwright e2e test**
+ **1 real, non-mocked system E2E journey** (8 stages, full stack) + **1 real,
non-mocked Docker Compose E2E journey** (full container topology) + **4 PDF service
tests** = **301 tests, 0 failing**.

This report reflects the fully-merged, CI-green state of PR #3 — every gate above is
either a genuinely observed PASS or an honestly labeled NOT_VERIFIED with its exact
reason; nothing here is an assumption.
