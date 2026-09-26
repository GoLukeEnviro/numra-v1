# AVENYTH

*(technical namespace: `numra` — packages, DB identifiers and internal infra keep
the original working name; see [Naming](#naming))*

[![CI](https://github.com/GoLukeEnviro/numra-v1/actions/workflows/ci.yml/badge.svg)](https://github.com/GoLukeEnviro/numra-v1/actions/workflows/ci.yml)

**AVENYTH does not guess.**

## What AVENYTH is

AVENYTH is a **Personal & Relationship Development OS built on deterministic
numerology**. A pure-Python calculation core derives every numerological value from a
documented formula ([`specs/canon-spec.md`](specs/canon-spec.md)) — the same input
always produces the same output, with a hash to prove it. Curated knowledge content
and a user's own structured evidence (check-ins, tasks, roadmaps, shared reflections)
feed an LLM that *interprets and explains* what the engine already computed — it never
performs an authoritative calculation and never invents a value, a score, or a claim:

> Numerology provides context. User data provides evidence. Deterministic/statistical
> services calculate. The LLM interprets and renders.
> **NO EVIDENCE → NO CLAIM.**

AVENYTH is not a generic habit tracker, a dating/swipe app, a social network, or a
classic horoscope app. It is deliberately serious on two levels at once — individual
development and relationship development — for people who want *evidence*, not
predictions. There is no invented compatibility percentage: relationship comparisons
are shown metric by metric, never collapsed into a fabricated score.

## Current delivery status

The responsive web application / installable PWA (`apps/web`) is the canonical
AVENYTH client. The full V2 relationship feature set — roadmaps, shared reflections,
private/shared Copilot, workspace dissolution and privacy closure, the evidence
layer — is implemented, and the project is in **Product Closure**. Native mobile
(`apps/mobile`) is deliberately frozen: the historical MOBILE-12A/B/C code remains in
the repository but sees no new feature work. The single current source of truth for
delivery status, open blockers and next actions is
[docs/planning/avenyth-pwa-execution-state.md](docs/planning/avenyth-pwa-execution-state.md).

**Core principle: AVENYTH does not guess.** Every numerological value comes from
`packages/engine-numerology`, a network-free, database-free, LLM-free Python package
with a fully documented formula for every metric it computes
(`specs/canon-spec.md`). Anything not explicitly specified is marked
`RESERVED_UNFROZEN` or `FEATURE_DISABLED_NO_CANON` and is never faked — see
[docs/adr/006-unfrozen-features.md](docs/adr/006-unfrozen-features.md). The same
discipline applies to newer decisions: the element/water system has no canonical
source anywhere in the project and stays `FEATURE_DISABLED_NO_CANON` rather than
being invented — see
[docs/adr/015-element-water-system-open-decision.md](docs/adr/015-element-water-system-open-decision.md).

## Project overview

```
Person input → normalization → deterministic engine → Canonical Profile (+ hash)
  → knowledge resolution → interpretation / relationship-interpretation composition
  → safety/claim validation → CLI / API / long-form report pipeline / web / PDF
```

An LLM is used only to *explain* values the engine already computed — never to compute
them. See [docs/adr/003-llm-not-calculator.md](docs/adr/003-llm-not-calculator.md).

## Architecture

| Path | Responsibility |
|---|---|
| `packages/engine-numerology` | Deterministic calculation core. No I/O of any kind. |
| `packages/engine-interpretation` | Knowledge loader, rule-based interpretation composer, LLM provider interface (Mock + Ollama Cloud), long-form report pipeline (`report/`). |
| `packages/engine-relationship-interpretation` | V2 relationship/shadow-dynamics interpretation composer: two Canonical Profiles + relationship-frame knowledge → structured analysis, no compatibility score. |
| `packages/engine-astrology` | Typed interface only — `FEATURE_DISABLED_NO_CANON`. |
| `packages/schema` | Generated TypeScript client (`openapi-typescript`) from `openapi/numra-v1.json`. Do not hand-edit `src/generated/`. |
| `apps/api` | Stateless FastAPI app: auth, people, calculations, relationships, reports, workspaces, check-ins, tasks, admin, account deletion. |
| `apps/api` (worker) | `python -m numra_api.worker` — the report job queue's poller, same codebase as the API, different entrypoint. |
| `apps/web` | Next.js/React/TypeScript frontend — the canonical installable PWA client. |
| `apps/pdf` | Internal Playwright/Chromium PDF rendering service (no public URL surface). |
| `apps/mobile` | Expo/React Native app. **Frozen** — historical MOBILE-12A/B/C code, no active development. |
| `knowledge/` | Versioned German interpretive content (`knowledge_version` in `manifest.yaml`). |
| `specs/` | `canon-spec.md` (the formal calculation spec), `profile.schema.json`, the V2 spec suite (`specs/v2/`), per-phase evidence. |
| `openapi/numra-v1.json` | The OpenAPI spec `packages/schema`'s TypeScript client is generated from. |
| `fixtures/canonical/lukas-springer.v1.json` | The golden reference profile (see below). |

Import order is enforced pipeline-first: `numra_numerology → numra_interpretation →
numra_api`. The engine has zero imports from any other AVENYTH/NUMRA package.

## Naming

**AVENYTH** is the product name (formerly "Numra" up to PR-WEB-00B; that name is
banned from all user-visible text — enforced by
`apps/web/src/__tests__/brand-guard.test.ts`). Purely technical identifiers
(`@numra/web`, `@numra/pdf`, `@numra/schema`, `numra_api`, Python package names, DB/
migration names, cache/LocalStorage keys) deliberately keep the original `numra`
name — renaming internal infrastructure with no user-facing benefit is unnecessary
risk. See [docs/brand/visual-identity.md](docs/brand/visual-identity.md) for the full
brand guideline.

## Requirements

- Python 3.11+, [`uv`](https://docs.astral.sh/uv/)
- Node.js 20+, `pnpm` (`corepack enable` or `npm i -g pnpm`)
- PostgreSQL 16 (local install or Docker)
- Docker + Docker Compose (optional, for the full containerized stack)

## Installation

```bash
uv sync --all-packages --all-groups
pnpm install
```

## Environment

Copy `.env.example` to `.env` and fill in real values. The app starts and stays
healthy with `NUMRA_LLM_PROVIDER=disabled` (the default) and no Ollama key — report
generation fails fast with a clear `LLM_UNAVAILABLE` error rather than crashing
(`GET /v1/health/ready` reports `"llm": "disabled"`). `NUMRA_LLM_PROVIDER=mock` is only
permitted outside `ENVIRONMENT=production` — the app refuses to start otherwise.

## Local development

```bash
# Postgres (local install)
sudo service postgresql start
sudo -u postgres psql -c "CREATE USER numra WITH PASSWORD 'numra_dev_password' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE numra_dev OWNER numra;"

# Database schema
cd apps/api && uv run alembic upgrade head && cd ../..

# API
uv run uvicorn numra_api.app:app --reload --port 8000 --app-dir apps/api/src

# Worker (separate terminal)
uv run python -m numra_api.worker --app-dir apps/api/src  # or: cd apps/api/src && uv run python -m numra_api.worker

# Web (separate terminal)
pnpm --filter @numra/web dev   # http://localhost:3000, expects the API on :8000

# PDF service (separate terminal)
cd apps/pdf && PDF_INTERNAL_TOKEN=dev-token node src/server.js   # :4300
```

## Database migrations

```bash
cd apps/api
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "description"   # after model changes
uv run alembic downgrade base && uv run alembic upgrade head   # verify both directions
```

## Tests

```bash
# Python — from repo root
uv run pytest packages/engine-numerology/tests packages/engine-interpretation/tests \
  packages/engine-relationship-interpretation/tests -q \
  --cov=packages/engine-numerology/src/numra_numerology --cov-report=term-missing
uv run coverage report --include="packages/engine-numerology/src/numra_numerology/*" --fail-under=90
uv run pytest apps/api/tests -q   # needs a running Postgres (TEST_DATABASE_URL
                                   # or the apps/api/tests/conftest.py default)
uv run ruff format --check . && uv run ruff check .
uv run mypy apps/api/src packages/engine-numerology/src packages/engine-interpretation/src packages/engine-relationship-interpretation/src packages/engine-astrology/src

# Web
pnpm --filter @numra/web lint
pnpm --filter @numra/web exec tsc --noEmit
pnpm --filter @numra/web test -- --run
pnpm --filter @numra/web build
pnpm --filter @numra/web exec playwright test

# PDF service
cd apps/pdf && node --test src/__tests__/render.test.js
```

CI (`.github/workflows/ci.yml`) runs 13 required checks on every PR: `lint-python`,
`python-typecheck`, `unit-and-property-tests`, `no-golden-leakage`,
`dependency-security`, `sast`, `schema-and-openapi-drift`,
`web-lint-typecheck-build-test`, `pdf-service-tests`, `docker-build`,
`docker-compose-e2e`, `playwright`, `system-e2e`.

## Docker

```bash
cp .env.example .env   # fill SESSION_SECRET / PDF_INTERNAL_TOKEN at minimum
docker compose config --quiet   # validate
docker compose up --build
curl --fail http://127.0.0.1:8000/v1/health/ready
```

Services: `postgres`, `migrate` (one-shot, runs Alembic then exits), `api`, `worker`,
`analysis-worker`, `redis`, `pdf`, `web`. See `docker-compose.yml` and
`docker/*.Dockerfile`.

## LLM configuration (Ollama Cloud)

`NUMRA_LLM_PROVIDER` is the single source of truth for which LLM backend the worker
uses — `numra_api.services.llm_factory.build_llm_provider` is the only place a concrete
provider class is chosen, and nothing falls back silently between providers:

- `disabled` (default) — no LLM call is ever attempted; report generation fails fast
  with `LLM_UNAVAILABLE`. Safe default; the app and worker stay healthy.
- `ollama` — real Ollama Cloud calls. Also set `OLLAMA_BASE_URL`, `OLLAMA_API_KEY`.
  Model names (`NUMRA_LLM_MODEL_PREMIUM`/`NUMRA_LLM_MODEL_FAST`) are configuration
  defaults, not a guarantee of live availability — see `specs/evidence/phase-3.md` and
  `specs/evidence/phase-4.md` for what is and isn't verified against a real provider in
  this build.
- `mock` — deterministic, network-free canned content (`MockLLMProvider`). Only
  permitted when `ENVIRONMENT` is not `production`; the app refuses to start otherwise
  (`Settings` validates this at construction time). Used by the test suite and local
  dev, never served to a real user.

## PDF service

Internal-only; requires a bearer token (`PDF_INTERNAL_TOKEN`) and never accepts a
caller-supplied URL (see [docs/adr/005-pdf-rendering.md](docs/adr/005-pdf-rendering.md)).
`POST /render/report` with `{report, profile, person}` (the same JSON shapes the API
returns) returns a PDF byte stream.

## Golden reference

`fixtures/canonical/lukas-springer.v1.json` — Lukas Springer, 1986-07-18, is the pinned
reference profile every phase's tests check against (Life Path `22/4`, Expression
`62/8`, Soul Urge `18/9`, Personality `44/8`, ...). Production code is statically
checked to never special-case this person (`test_no_golden_leakage.py`).

## Known unfrozen features

Astrology, Essence, Name/Physical/Mental/Spiritual Transits, Planes of Expression,
relationship compatibility percentages, Period Cycle date-boundary transitions, and the
element/water system are **not implemented** — see
[docs/adr/006-unfrozen-features.md](docs/adr/006-unfrozen-features.md),
[docs/adr/015-element-water-system-open-decision.md](docs/adr/015-element-water-system-open-decision.md)
and `specs/canon-spec.md` §26/§32/§33.

## Architecture decisions

Every durable technical and product decision is recorded as an ADR in
[docs/adr/](docs/adr/) — from the deterministic-engine and LLM-not-calculator
foundations (001, 003) through the V2 relationship architecture, consent model, LLM
grounding, managed minor profiles, workspace dissolution and offline navigation
(008–014), to the most recent element/water scope decision (015). Read the execution
state doc above first; the ADRs explain *why*, not *what's shipped right now*.

## Release history

- **V1.5 — product completion.** Server-authoritative calculation/report/relationship
  history, a full person-profile edit workflow with immutable calculation snapshots,
  append-only identity history, a report library, a relationship library with
  knowledge-sourced qualitative notes (still no compatibility score), a
  German-default/English-switchable UI, a mobile-first bottom nav, an installable PWA,
  an expanded deterministic interpretation engine (Hidden Passion, Karmic Lessons,
  Pinnacles, Challenges, Personal Year/Month/Day, ...), a deterministic reflective
  Daily Brief (no LLM), calculation snapshot comparison, per-section report
  provenance, and Settings V2. None of it touches `calculation_version` or the golden
  canon. See [docs/adr/007-v1-5-product-completion.md](docs/adr/007-v1-5-product-completion.md).
- **V1.6 A — RBAC and admin backend.** `role` (`USER`/`ADMIN`) and `is_active` on
  `User`, an admin-only API gated end-to-end by `require_admin`, and an append-only
  `admin_audit_events` table. A disabled account is indistinguishable from a wrong
  password in every response.
- **V1.6 B — public platform and admin console.** A real landing page, public config
  endpoint, self-service registration with auto-login, a first-run onboarding flow, an
  admin console frontend, and complete i18n across every surface (numerology
  terminology stays English by design). Self-signup rolls out only as an explicit,
  separately-verified step. See [docs/releases/v1.6-b.md](docs/releases/v1.6-b.md).
- **V2 — AVENYTH relationship core.** Relationship workspaces, roadmaps, shared
  reflections, private/shared Copilot, consent model, managed minor profiles,
  workspace dissolution and privacy closure, and the evidence layer, built additively
  on the V1.6 platform (`specs/v2/`, ADRs 008–014). Current status: **Product
  Closure** — see [Current delivery status](#current-delivery-status).

## Security notes

- Argon2id password hashing; session tokens are cryptographically random, only their
  SHA-256 hash is stored, cookies are `HttpOnly`/`SameSite=Lax`/`Secure` (in production).
- CSRF via double-submit cookie (`numra_csrf` + `x-csrf-token` header) on every
  state-changing request.
- `ALLOW_SELF_SIGNUP` defaults to `false`.
- Structured, machine-readable error codes everywhere (`services/errors.py`) — no
  silent fallbacks (§156 of the original spec: the app never catches an error and
  returns a default/random value).
- PII-safe logging: access logs and LLM-generation logs never contain names, birth
  data, or full prompts — only IDs, status, latency (`middleware/security.py`,
  `models/tables.py::LLMGeneration`).
- Dependency security audit: `pnpm audit --prod` (Node/web), `uvx pip-audit` (Python),
  and `bandit` (SAST, MEDIUM+ gate) — all run as explicit CI gates
  (`dependency-security` and `sast` jobs, `.github/workflows/ci.yml`) that fail the
  build on a fixable Critical/High production advisory or a new MEDIUM+ finding.

## Privacy notes

`POST /v1/account/delete-all` requires password re-confirmation and CSRF, then deletes
the `User` row; every dependent table (`people`, `name_identities`, `calculations`,
`relationships`, `reports`, `report_sections`, `report_jobs`, `llm_generations`,
`exports`, `sessions`) cascades at the database level (`ondelete="CASCADE"` on every
relevant foreign key) — verified end-to-end in
`apps/api/tests/integration/test_delete_all.py`.

## Troubleshooting

- **`alembic upgrade head` fails to connect** — check `DATABASE_URL`/`TEST_DATABASE_URL`
  and that Postgres is actually running (`pg_isready`).
- **`GET /v1/health/ready` shows `"llm": "disabled"`** — expected with the default
  `NUMRA_LLM_PROVIDER=disabled`; report generation fails fast with `LLM_UNAVAILABLE`
  until you set `NUMRA_LLM_PROVIDER=ollama` with real `OLLAMA_BASE_URL`/`OLLAMA_API_KEY`
  credentials (or `NUMRA_LLM_PROVIDER=mock` outside production, for local dev/tests).
- **Playwright can't find Chromium** in a sandboxed/dev environment with a
  non-standard install path — see `PLAYWRIGHT_CHROMIUM_PATH` in `apps/pdf/src/server.js`
  and the `executablePath` override pattern in `apps/pdf/src/__tests__/render.test.js`
  / `apps/web/playwright.config.ts`.
- **`docker compose up` fails without a running Docker daemon** — this is an external
  environment dependency, not a code issue; see `specs/evidence/phase-6.md`.
