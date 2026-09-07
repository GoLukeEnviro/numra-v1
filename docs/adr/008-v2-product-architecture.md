# ADR 008 — AVENYTH V2 Is Additive, Not a Rewrite

## Status

Accepted.

## Context

NUMRA V1.6 is a working, production-deployed platform: deterministic canon, golden
fixtures, FastAPI + PostgreSQL, server-side sessions, reports, LLM abstraction, PWA,
Today/Timing, Relationships V1, RBAC/Admin, PDF, CI (12 required checks), Docker,
production deployment. The AVENYTH V2 product vision (personal + relationship
development, configurable check-ins, shared/private Copilot, evidence-based
patterns) is a large surface expansion. The risk of a parallel rewrite is losing the
already-verified canon, golden fixtures, and production hardening built up over
V1–V1.6.

## Decision

AVENYTH V2 is built **additively** on the existing repository and stack. No new
repository, no rewrite of `packages/engine-numerology`, no replacement of the
existing FastAPI/PostgreSQL/session/PWA stack. Branding changes user-facing text
only (`APP_BRAND_NAME=AVENYTH`); technical namespaces (`numra_*`) are left alone
during the V2 core rebuild — branding is not a canon migration and renaming them is
pure risk with no product value. The repository stays `GoLukeEnviro/numra-v1` for
the duration of the core rebuild.

All 12 existing required CI checks (`lint-python`, `python-typecheck`,
`unit-and-property-tests`, `no-golden-leakage`, `dependency-security`,
`schema-and-openapi-drift`, `web-lint-typecheck-build-test`, `pdf-service-tests`,
`docker-build`, `docker-compose-e2e`, `playwright`, `system-e2e`) remain mandatory
for every V2 PR; new phase-specific checks are added, never substituted in place of
existing ones.

Feature work proceeds gate-by-gate per the phase list in
`specs/v2/api-contract.md` §PR structure, each phase gated on the previous one being
green, with feature flags keeping unfinished phases dark in production.

## Consequences

- A V2 PR that breaks an existing V1.6 behavior (Today, Reports, RBAC/Admin, PDF) is
  treated as a regression, not an acceptable cost of the rebuild.
- Full specs (`specs/v2/*.md`) are frozen before feature code begins (Phase 0 gate).
- A future, separate decision would be needed to actually rename technical
  namespaces or the repository — this ADR does not authorize that.
