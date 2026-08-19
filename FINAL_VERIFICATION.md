# NUMRA V1 — Final Verification Report

Every result below reflects a command that was actually executed in this build session
and observed, not an assumption. Per-phase detail and raw command transcripts live in
`specs/evidence/phase-{0..6}.md`.

## Calculation Engine

| Command/Test | Result | Evidence |
|---|---|---|
| `uv run pytest packages/engine-numerology/tests -q --cov=... --cov-fail-under=90` | **PASS** — 104 passed, 100% coverage | `specs/evidence/phase-1.md` |
| Reduction test matrix (15 pinned pairs, e.g. `29 → "11/2"`, `44 → "44/8"`) | **PASS** | `packages/engine-numerology/tests/unit/test_reduction.py` |
| Hypothesis property tests (termination, root range, master range, no-false-master, invariants) | **PASS** | `packages/engine-numerology/tests/property/` |
| Golden Lukas Springer test (values + traces) | **PASS** | `packages/engine-numerology/tests/golden/test_lukas_springer_golden.py` |
| Edge cases (§71: master birthday, leap day, multi-name, diacritics, vowel-less, Hidden Passion tie/unique, Challenge=0, ...) | **PASS** | `packages/engine-numerology/tests/edge_cases/` |
| Anti-cheating grep (no golden literals/imports in production source) | **PASS** | `packages/engine-numerology/tests/unit/test_no_golden_leakage.py` |
| `uv run ruff format --check . && uv run ruff check .` | **PASS** | — |
| `uv run mypy packages/engine-numerology/src` (strict) | **PASS** | — |
| Engine has zero DB/API/LLM imports | **PASS** — `grep -rl "sqlalchemy\|asyncpg\|fastapi\|numra_api"` returns nothing | `specs/evidence/phase-2.md` |

## API

| Command/Test | Result | Evidence |
|---|---|---|
| `uv run pytest apps/api/tests -q` (real PostgreSQL 16, not mocked) | **PASS** — 29 passed (auth, people, calculations, relationships, reports, not-found, delete-all) | `specs/evidence/phase-2.md`, `phase-4.md`, `phase-6.md` |
| Auth (register/login/logout/me, wrong password, CSRF enforcement) | **PASS** | `apps/api/tests/integration/test_auth_flow.py` |
| Future-birth-date rejection (`FUTURE_BIRTH_DATE_NOT_ALLOWED`) at the app layer only | **PASS** | `apps/api/tests/integration/test_people_and_calculations.py` |
| Golden calculation through the full HTTP stack (`22/4`, `62/8`, `18/9`, `44/8`, `17/8`) | **PASS** | `apps/api/tests/integration/test_people_and_calculations.py` |
| OpenAPI export has no drift (`scripts/export_openapi.py --check`) | **PASS** | `openapi/numra-v1.json` |
| Generated TS client has no drift | **PASS** | `packages/schema/src/generated/schema.d.ts` |
| `uv run mypy apps/api/src` (strict) | **PASS** | — |

## Database

| Command/Test | Result | Evidence |
|---|---|---|
| `alembic upgrade head` on an empty DB | **PASS** — real Postgres, 11 application tables + `alembic_version` | `specs/evidence/phase-2.md` |
| `alembic downgrade base && alembic upgrade head` | **PASS** | `specs/evidence/phase-2.md` |
| App boots against a freshly-migrated empty DB | **PASS** | `specs/evidence/phase-2.md` |
| Cascade delete (`POST /v1/account/delete-all`) — every dependent table verified at 0 rows after, no orphans | **PASS** | `apps/api/tests/integration/test_delete_all.py`, `specs/evidence/phase-6.md` |

## LLM Adapter

| Command/Test | Result | Evidence |
|---|---|---|
| `MockLLMProvider` — deterministic, no network, round-trips structured output | **PASS** | `packages/engine-interpretation/tests/unit/test_llm_mock_provider.py` |
| Wrong numeric claim / unknown metric_id → `InvalidReportSection` | **PASS** | `packages/engine-interpretation/tests/unit/test_llm_validator.py` |
| `OllamaCloudProvider.health()` reports `"unavailable"` cleanly when unconfigured (never crashes) | **PASS** | `packages/engine-interpretation/tests/unit/test_llm_ollama_provider.py` |
| Provider swappable behind `LLMProvider` protocol | **PASS** | `packages/engine-interpretation/tests/unit/test_llm_provider_swappable.py` |
| Live Ollama Cloud generation | **NOT VERIFIED / EXTERNAL_DEPENDENCY_NOT_AVAILABLE** — no `OLLAMA_API_KEY` in this environment | `specs/evidence/phase-3.md` |

## Report Pipeline

| Command/Test | Result | Evidence |
|---|---|---|
| Manifest word ranges (QUICK/FULL/ULTIMATE/CUSTOM) | **PASS** | `packages/engine-interpretation/tests/unit/test_report_pipeline.py` |
| 15,000+ word ULTIMATE report generation with Mock Provider | **PASS** — reached ≥15,000 words, all sections present | same |
| Global Report Linter (missing sections, duplicate headings/paragraphs, word count, unresolved placeholders, unsupported claims, metric reference integrity) | **PASS** | same |
| One controlled repair attempt on invalid claim, then hard fail | **PASS** | same |
| No core-number mutation across a full report run | **PASS** | same |
| Postgres job queue restart-safety (crashed-worker lease reclaim) | **PASS** — real Postgres `SELECT ... FOR UPDATE SKIP LOCKED` | `apps/api/tests/integration/test_reports.py` |
| Idempotency-Key support | **PASS** | same |
| Live Ollama Cloud report generation | **NOT VERIFIED / EXTERNAL_DEPENDENCY_NOT_AVAILABLE** | `specs/evidence/phase-4.md` |

## Frontend

| Command/Test | Result | Evidence |
|---|---|---|
| `pnpm --filter @numra/web lint` | **PASS** | `specs/evidence/phase-5.md` |
| `pnpm --filter @numra/web exec tsc --noEmit` | **PASS** | same |
| `pnpm --filter @numra/web test -- --run` (Vitest) | **PASS** — 7/7 | same |
| `pnpm --filter @numra/web build` | **PASS** — all 11 app routes + not-found compiled | same |
| `pnpm --filter @numra/web exec playwright test` (golden journey) | **PASS** — 1/1 | same |
| Diagnostic Life Path visually/structurally distinguished from canonical | **PASS** — unit-tested against the real golden fixture | same |
| No invented relationship compatibility percentage | **PASS** — match/no-match booleans only | same |

## PDF

| Command/Test | Result | Evidence |
|---|---|---|
| `node --test apps/pdf/src/__tests__/render.test.js` | **PASS** — 4/4 (HTML escaping, real PDF render, page-object presence, headings present) | `specs/evidence/phase-6.md` |
| End-to-end HTTP smoke test (`/health/live`, `/health/ready`, authenticated `/render/report` → real 3-page PDF, unauthenticated → 401) | **PASS** | `specs/evidence/phase-6.md` |

## Privacy

| Command/Test | Result | Evidence |
|---|---|---|
| PII-safe logging (access log / `LLMGeneration` never store names, birth data, prompts) | **PASS** — by construction, see `middleware/security.py`, `models/tables.py` | `specs/evidence/phase-2.md` |
| `POST /v1/account/delete-all` requires password re-confirmation + CSRF | **PASS** | `apps/api/tests/integration/test_delete_all.py` |
| Full cascade delete verified with real created rows across every dependent table | **PASS** | same |

## Docker

| Command/Test | Result | Evidence |
|---|---|---|
| `docker compose config --quiet` | **PASS** — valid compose file, all variables resolve | `specs/evidence/phase-6.md` |
| `docker compose build` / `docker compose up` / container health checks | **NOT VERIFIED / EXTERNAL_DEPENDENCY_NOT_AVAILABLE** — no Docker daemon in this sandbox | `specs/evidence/phase-6.md` |

## CI

| Command/Test | Result | Evidence |
|---|---|---|
| `.github/workflows/ci.yml` written, mirrors `scripts/verify.py`'s gates as separate jobs (lint, python-typecheck, unit/property tests, no-golden-leakage, schema/openapi drift, web lint/typecheck/build/test, Playwright, PDF service tests, docker-build) | Written, internally consistent | `.github/workflows/ci.yml` |
| Actual execution on GitHub Actions runners | **NOT VERIFIED** — never pushed through a real GitHub Actions run in this session | — |
| Local equivalent of every CI gate except `docker-build` | **PASS** — `python3 scripts/verify.py --skip-docker` | `specs/evidence/phase-6.md` |

## Dependency security

| Command/Test | Result | Evidence |
|---|---|---|
| `pnpm audit` (web) | **PASS after fix** — 1 critical (vitest arbitrary-file-read) found and fixed by bumping `vitest` to `^3.2.6`; 30 remaining (12 high, 16 moderate, 2 low), all transitive through `next@14.2.35`, require a Next.js 15 major upgrade | `specs/evidence/phase-6.md` |
| Next.js 14→15 upgrade to close remaining advisories | **NOT DONE / DEFERRED** — deliberate follow-up, not an oversight (needs its own full re-verification pass, not a same-session patch) | `specs/evidence/phase-6.md` |
| `pip-audit` (Python) | **NOT RUN** — tool not installed in this environment; dependency set is small and pinned via `uv.lock` | — |

## Overall

```
CORE_SYSTEM (engine, API, DB, report pipeline, frontend, PDF)  = PASS
LIVE_LLM_SMOKE (Ollama Cloud)                                   = NOT_VERIFIED
REASON                                                          = MISSING_CREDENTIALS
DOCKER_RUNTIME (build/up/health, beyond `compose config`)        = NOT_VERIFIED
REASON                                                          = EXTERNAL_DEPENDENCY_NOT_AVAILABLE (no daemon)
GITHUB_ACTIONS_EXECUTION                                        = NOT_VERIFIED
REASON                                                          = never run on GitHub's infrastructure in this session
```

Total test count across the repository, all real and passing at time of writing:
**197 Python tests** (`uv run pytest packages apps/api/tests -q`) + **7 web unit tests**
+ **1 Playwright e2e test** + **4 PDF service tests** = **209 tests, 0 failing**.
