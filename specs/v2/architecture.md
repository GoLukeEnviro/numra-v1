# AVENYTH V2 — Architecture

## Status

Draft — Phase 0 spec freeze.

## Baseline

Current `main` (baseline SHA recorded at Phase-0 recon time: `8d24928b`, CI green on
all 12 required checks). V2 is built additively on:

- `packages/engine-numerology` (frozen canon, unchanged)
- `packages/engine-interpretation` (LLM prompt/report pipeline)
- `packages/engine-astrology` (reserved/unfrozen interface, ADR 006)
- `packages/schema`
- `apps/api` (FastAPI + PostgreSQL + SQLAlchemy)
- `apps/web` (Next.js PWA)
- `apps/pdf`
- Existing auth (opaque server-side sessions), RBAC/Admin, CI (12 required checks),
  Docker/Compose, production deployment.

No rewrite. No parallel stack. See `docs/adr/008-v2-product-architecture.md`.

## Absolute invariants (carried over, non-negotiable)

1. `packages/engine-numerology` stays deterministic, network-free, DB-free,
   LLM-free. Same input → same output.
2. Existing canon versions and golden fixtures are never cosmetically altered.
3. The LLM never performs an authoritative calculation — not Life Path, Expression,
   Soul Urge, Personality, Timing, Pinnacles, Challenges, Karmic Lessons, Hidden
   Passion, compatibility %, check-in gaps, trends, correlations, scores, sample
   sizes, or effect sizes. All of these are deterministic/statistical service output
   only (`specs/v2/evidence-policy.md`, `specs/v2/checkin-spec.md`).

## Brand configuration

Public-facing brand: **AVENYTH**. Technical namespaces (`numra_numerology`,
`numra_interpretation`, `numra_api`, `numra-canonical`, existing DB identifiers,
migration history, canonical IDs, hash inputs, fixture IDs, `calculation_version`)
are **not** renamed in V2 Core — branding is not a canon migration.

Introduce a single source of truth for the display name, e.g. an environment /
config value `APP_BRAND_NAME=AVENYTH` consumed by web templates, email templates,
and PDF headers. Document the technical-vs-brand-name split in
`docs/adr/008-v2-product-architecture.md`.

Repository stays `GoLukeEnviro/numra-v1` for the duration of the V2 core rebuild — no
repository rename.

## New V2 subsystems (additive)

- Auth extensions: email verification, forgot/reset password
  (`specs/v2/api-contract.md`).
- Entitlements service (`specs/v2/api-contract.md`).
- Personal Workspace (`specs/v2/personal-workspace-spec.md`), built around the
  existing `Person`/`Calculation` model — no duplication of `CanonicalProfile`.
- Connections + Consent (`specs/v2/connection-spec.md`,
  `specs/v2/consent-spec.md`).
- Relationship Workspace (`specs/v2/relationship-workspace-spec.md`,
  `specs/v2/relationship-type-spec.md`, `specs/v2/shadow-dynamics-spec.md`).
- Configurable Check-ins (`specs/v2/checkin-spec.md`).
- Shared Tasks + Roadmaps (`specs/v2/task-system-spec.md`,
  `specs/v2/roadmap-spec.md`).
- Copilot (private + shared) (`specs/v2/copilot-grounding-spec.md`).
- Managed Minor Profiles (`specs/v2/minor-profile-policy.md`).
- Dissolution / account deletion (`specs/v2/dissolution-policy.md`).
- Evidence Layer — Phase 6 only (`specs/v2/evidence-policy.md`).

## Database

PostgreSQL stays authoritative. Normalized relational tables for ownership,
membership, permissions, consent, state, timestamps. JSONB only for versioned
structured generated content, snapshot payloads, and validated LLM structured
output — never as the sole storage of a critical authorization rule
(`specs/v2/data-model.md`).

Row-Level Security is evaluated, not assumed — see
`docs/adr/010-v2-consent-model.md` for the RLS-adopted-or-deferred decision.
Application-level authorization remains mandatory either way.

## Concurrency & realtime

Optimistic concurrency (`version`/`updated_at`/ETag-style `If-Match`) for edit
conflicts — no CRDT/OT in V2 Core. REST by default; SSE/streaming only for LLM
response streaming; no general WebSocket introduction without a demonstrated need.

## LLM provider

Existing Ollama provider stays primary; provider abstraction is kept and improved,
not replaced. No silent fallback between providers. On provider failure: canonical
engine and relationship calculations stay available; LLM operations surface as
`QUEUED` / `RETRYABLE` / `UNAVAILABLE` states to the UI.

## Delivery surface

Web/PWA (existing Next.js app) first and complete for V2 Core. Native mobile
(`apps/mobile`, Expo/React Native) starts only after V2 Core acceptance
(`specs/v2/roadmap-spec.md` §Native Mobile is out of scope here).

## Feature flags

`AVENYTH_V2_ENABLED`, `AVENYTH_CONNECTIONS_ENABLED`,
`AVENYTH_RELATIONSHIP_WORKSPACES_ENABLED`, `AVENYTH_CHECKINS_ENABLED`,
`AVENYTH_TASKS_ENABLED`, `AVENYTH_COPILOT_ENABLED`,
`AVENYTH_EVIDENCE_LAYER_ENABLED`. New phases stay disabled in production until their
phase's acceptance gate (`specs/v2/roadmap-spec.md`) passes.
