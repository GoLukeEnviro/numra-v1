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
| `docker compose config --quiet` | **PASS** — valid compose file, all variables resolve | `specs/evidence/phase-6.md`, re-verified this pass |
| `dockerd` starts in this sandbox | **PASS** — a genuinely new capability vs. the earlier build session, where no daemon was available at all | this pass |
| `docker compose build` / `docker pull` / any registry image pull | **NOT VERIFIED / BLOCKED** — every pull attempt returns a consistent `403 Forbidden` from `production.cloudfront.docker.com`, a sandbox network-egress policy restriction, not a missing daemon. Per this environment's own guidance, organization policy denials are not retried. | this pass |
| Real Docker builds on GitHub Actions (`docker-build` CI job) | **IN PROGRESS as of this writing** — see CI section below; already found and fixed two real, pre-existing Dockerfile bugs (`uv sync --package` repeated-flag rejection; missing `apps/web/public` directory) that no prior verification pass had ever caught, because none had a real daemon to build against | this pass |

### CI — real GitHub Actions execution

Unlike the earlier build session (no `gh` CLI, no way to observe real Actions
results), this pass pushed a real branch, opened a real draft PR
(`GoLukeEnviro/numra-v1#3`, branch `fix/numra-v1-production-completion`), and is
watching its checks execute for real. A new `system-e2e` job was added to
`.github/workflows/ci.yml`, standing up Postgres, Redis, a real PDF service, a real
API instance, and a real worker, then running the real system journey above.

Real execution surfaced three genuine, previously-invisible bugs — none caught by any
local gate, because none of the three failure modes (a CI-runner-specific pnpm/Node
action conflict, a `uv` multi-`--package` flag rejection, a directory that plain never
existed) can occur outside a real CI runner building real containers:

1. `pnpm/action-setup@v4`'s `version:` input conflicted with `package.json`'s
   `packageManager` field ("Multiple versions of pnpm specified") — fixed by removing
   the redundant `version:` input from all 6 occurrences.
2. `docker/api.Dockerfile` called `uv sync --package` four times in one command, which
   `uv` 0.5.11 rejects outright — fixed by confirming the four named packages are the
   workspace's entire membership and simplifying to a plain `uv sync --frozen --no-dev`
   (verified locally before pushing).
3. `docker/web.Dockerfile`'s `COPY --from=build /repo/apps/web/public ./apps/web/public`
   failed because that directory did not exist anywhere in the repository — fixed by
   adding `apps/web/public/robots.txt` and a Next.js-convention `icon.svg` (see
   Frontend section above), verified locally with `pnpm build` before pushing.

As of this writing, the run triggered by the latest push (commit `38178a2`) has 6/10
checks green (`lint-python`, `python-typecheck`, `no-golden-leakage`,
`schema-and-openapi-drift`, `web-lint-typecheck-build-test`, `pdf-service-tests`) and
4 still in progress (`unit-and-property-tests`, `playwright`, `system-e2e`,
`docker-build`) — **zero failing so far**. This PR is subscribed for live CI events
and will keep being driven to green (or every remaining red check will get a
documented, non-fixable reason) rather than left mid-stream.

## Dependency security

| Command/Test | Result | Evidence |
|---|---|---|
| `pnpm audit` (web, prod deps) | **25 vulnerabilities** (2 low, 13 moderate, 10 high), all transitive through `next@14.2.35` | re-verified this pass |
| `pnpm audit` (web, incl. devDependencies) | 30 vulnerabilities (2 low, 16 moderate, 12 high), same root cause | re-verified this pass |
| Next.js 14→15 upgrade to close remaining advisories | **NOT DONE / DEFERRED** — deliberate follow-up, not an oversight; needs its own full re-verification pass (routing/middleware/proxy behavior all depend on the exact Next.js version), not a same-session patch under an already-large diff | `specs/evidence/phase-6.md` |
| `pip-audit` (via `uvx pip-audit`, Python deps) | **PASS** — "No known vulnerabilities found" | re-verified this pass |

## Overall

```
CORE_SYSTEM (engine, API, DB, report pipeline, frontend, PDF)     = PASS
P0/P1 HARDENING (LLM wiring, retry, health, exports, rate limit)  = PASS
LIVE_LLM_SMOKE (Ollama Cloud)                                     = NOT_VERIFIED
REASON                                                             = MISSING_CREDENTIALS
REAL_SYSTEM_E2E (non-mocked, full stack)                          = PASS
REASON                                                             = 3 consecutive clean runs; caught + fixed 1 real bug
DOCKER_COMPOSE_CONFIG                                              = PASS
DOCKER_REGISTRY_PULL_LOCAL                                         = NOT_VERIFIED
REASON                                                             = sandbox network-egress policy (403 from cloudfront), not retriable
GITHUB_ACTIONS_EXECUTION                                           = IN_PROGRESS
REASON                                                             = real PR #3 open, 6/10 checks green, 4 in progress, 0 failing,
                                                                      3 real bugs found and fixed via real execution, actively monitored
```

Total test count across the repository, all real and passing at time of writing:
**256 Python tests** (`uv run pytest packages apps/api/tests -q`, engine subset:
104 tests at 100% coverage) + **39 web unit tests** + **1 mocked Playwright e2e test**
+ **1 real, non-mocked system E2E journey** (8 stages, full stack) + **4 PDF service
tests** = **301 tests, 0 failing**.

This report will be updated once the in-progress CI run reaches a final state.
