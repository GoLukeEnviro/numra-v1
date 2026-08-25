# NUMRA V1

A deterministic, auditable numerology platform: a pure-Python calculation engine, a
Postgres-backed FastAPI service, an LLM-assisted long-form report pipeline, a Next.js
web app, and an internal PDF renderer.

**Core principle: NUMRA does not guess.** Every numerological value comes from
`packages/engine-numerology`, a network-free, database-free, LLM-free Python package
with a fully documented formula for every metric it computes
(`specs/canon-spec.md`). Anything not explicitly specified is marked
`RESERVED_UNFROZEN` or `FEATURE_DISABLED_NO_CANON` and is never faked — see
[docs/adr/006-unfrozen-features.md](docs/adr/006-unfrozen-features.md).

## Project overview

```
Person input → normalization → deterministic engine → Canonical Profile (+ hash)
  → knowledge resolution → interpretation composition → safety/claim validation
  → CLI / API / long-form report pipeline / web / PDF
```

An LLM is used only to *explain* values the engine already computed — never to compute
them. See [docs/adr/003-llm-not-calculator.md](docs/adr/003-llm-not-calculator.md).

## Architecture

| Path | Responsibility |
|---|---|
| `packages/engine-numerology` | Deterministic calculation core. No I/O of any kind. |
| `packages/engine-interpretation` | Knowledge loader, rule-based interpretation composer, LLM provider interface (Mock + Ollama Cloud), long-form report pipeline (`report/`). |
| `packages/engine-astrology` | Typed interface only — `FEATURE_DISABLED_NO_CANON`. |
| `packages/schema` | Generated TypeScript client (`openapi-typescript`) from `openapi/numra-v1.json`. Do not hand-edit `src/generated/`. |
| `apps/api` | Stateless FastAPI app: auth, people, calculations, relationships, reports, account deletion. |
| `apps/api` (worker) | `python -m numra_api.worker` — the report job queue's poller, same codebase as the API, different entrypoint. |
| `apps/web` | Next.js/React/TypeScript frontend. |
| `apps/pdf` | Internal Playwright/Chromium PDF rendering service (no public URL surface). |
| `knowledge/` | Versioned German interpretive content (`knowledge_version` in `manifest.yaml`). |
| `specs/` | `canon-spec.md` (the formal calculation spec), `profile.schema.json`, per-phase evidence. |
| `fixtures/canonical/lukas-springer.v1.json` | The golden reference profile (see below). |

Import order is enforced pipeline-first: `numra_numerology → numra_interpretation →
numra_api`. The engine has zero imports from any other NUMRA package.

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
uv run pytest packages/engine-numerology/tests -q \
  --cov=packages/engine-numerology/src/numra_numerology --cov-fail-under=90
uv run pytest packages apps/api/tests -q   # needs a running Postgres (TEST_DATABASE_URL
                                            # or the apps/api/tests/conftest.py default)
uv run ruff format --check . && uv run ruff check .
uv run mypy apps/api/src packages/engine-numerology/src packages/engine-interpretation/src packages/engine-astrology/src

# Web
pnpm --filter @numra/web lint
pnpm --filter @numra/web exec tsc --noEmit
pnpm --filter @numra/web test -- --run
pnpm --filter @numra/web build
pnpm --filter @numra/web exec playwright test

# PDF service
cd apps/pdf && node --test src/__tests__/render.test.js
```

## Docker

```bash
cp .env.example .env   # fill SESSION_SECRET / PDF_INTERNAL_TOKEN at minimum
docker compose config --quiet   # validate
docker compose up --build
curl --fail http://127.0.0.1:8000/v1/health/ready
```

Services: `postgres`, `migrate` (one-shot, runs Alembic then exits), `api`, `worker`,
`pdf`, `web`. See `docker-compose.yml` and `docker/*.Dockerfile`.

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
relationship compatibility percentages, and Period Cycle date-boundary transitions are
**not implemented** — see
[docs/adr/006-unfrozen-features.md](docs/adr/006-unfrozen-features.md) and
`specs/canon-spec.md` §26/§32/§33.

## V1.5 — product completion

On top of the frozen V1 canon above, V1.5 added: server-authoritative calculation/
report/relationship history (a fresh browser with no LocalStorage still sees
everything), a full person-profile edit workflow (calculation snapshots stay
immutable — editing never rewrites one), real append-only identity history, a report
library, a relationship library with knowledge-sourced qualitative notes (still no
compatibility score), a German-default/English-switchable UI, a mobile-first bottom
nav, an installable PWA (its service worker never caches anything under `/api/`), an
expanded deterministic interpretation engine (Hidden Passion, Karmic Lessons,
Pinnacles, Challenges, Personal Year/Month/Day, ...), a deterministic reflective Daily
Brief (no LLM), calculation snapshot comparison, per-section report provenance, and
Settings V2 (password change with other-session revocation, session management,
sanitized system info). None of it touches `calculation_version` or the golden canon.
See [docs/adr/007-v1-5-product-completion.md](docs/adr/007-v1-5-product-completion.md)
for the durable decisions this introduced.

## V1.6 A — RBAC and admin backend

Adds `role` (`USER`/`ADMIN`) and `is_active` to `User`, an admin-only API
(`/v1/admin/stats`, `/users`, `/users/{id}`, `/users/{id}/disable`, `/enable`,
`/revoke-sessions`, `/audit`, gated end-to-end by `require_admin`), and an append-only
`admin_audit_events` table. A disabled account is indistinguishable from a wrong
password in every response — the same anti-enumeration idiom V1.5 already used for
ownership checks.

## V1.6 B — public platform and admin console

The frontend and self-service half of the account platform:

- **Public**: a real landing page at `/` (previously a hard redirect to `/login`),
  `GET /v1/public/config` (unauthenticated, capped to `self_signup_enabled`/`app_name`/
  `supported_ui_locales` — nothing environment- or deployment-specific), `/register`
  with auto-login (`POST /v1/auth/register` now issues the same session/CSRF cookies as
  login through one shared helper), and a short `/onboarding` first-run flow.
- **Admin console**: `/admin/login`, `/admin`, `/admin/users`, `/admin/users/[id]`,
  `/admin/audit` — a frontend for V1.6 A's backend. The route guard is explicitly *not*
  the security boundary in code comments; `require_admin` on the API is.
- **Complete i18n**: the flat `de.ts`/`en.ts` catalog is now split into
  `core`/`public`/`app`/`admin` modules per locale (still typed 1:1, plus a runtime
  catalog-parity test), covering every page including the new public and admin
  surfaces. Numerology terminology (Life Path, Personal Day, Master Number, ...) stays
  English by design — see `docs/releases/v1.6-b.md`.
- Self-signup rolls out only after the release is fully verified in production —
  `ALLOW_SELF_SIGNUP` stays `false` through merge and deploy, flipped to `true` as a
  separate, explicit step once the exact merge SHA is confirmed live.

See [docs/releases/v1.6-b.md](docs/releases/v1.6-b.md) for the full scope, security
boundaries, and production rollout evidence.

## Security notes

- Argon2id password hashing; session tokens are cryptographically random, only their
  SHA-256 hash is stored, cookies are `HttpOnly`/`SameSite=Lax`/`Secure` (in production).
- CSRF via double-submit cookie (`numra_csrf` + `x-csrf-token` header) on every
  state-changing request.
- `ALLOW_SELF_SIGNUP` defaults to `false`.
- Structured, machine-readable error codes everywhere (`services/errors.py`) — no
  silent fallbacks (§156 of the original spec: `NUMRA` never catches an error and
  returns a default/random value).
- PII-safe logging: access logs and LLM-generation logs never contain names, birth
  data, or full prompts — only IDs, status, latency (`middleware/security.py`,
  `models/tables.py::LLMGeneration`).
- Dependency security audit: `pnpm audit --prod` (Node/web) and `uvx pip-audit`
  (Python) — both run as an explicit CI gate (`dependency-security` job,
  `.github/workflows/ci.yml`) that fails the build on a fixable Critical/High
  production advisory.

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
