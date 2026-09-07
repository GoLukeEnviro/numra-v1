# AVENYTH V2 — Product Vision

## Status

Draft — Phase 0 spec freeze.

## One-line definition

AVENYTH is a **Personal & Relationship Development OS based on deterministic
numerology**.

It is not a generic habit tracker, a dating/swipe app, a social network, a classic
horoscope app, or an AI that computes numerology itself.

## The four layers

```
Canonical Engine
      |
Canonical Profile
      |
Knowledge Base
      |
Structured Personal / Relationship Context
      |
Deterministic Analysis Services
      |
LLM Renderer / Copilot
      |
Validated User-facing Insight
```

1. **Canonical Engine** — `packages/engine-numerology`. Deterministic, network-free,
   DB-free, LLM-free. Same input, same output, always (ADR 001).
2. **Curated Knowledge** — versioned interpretation content in `knowledge/`, keyed to
   canonical values, not written or invented at request time.
3. **Structured Workspace Evidence** — data a user or a connected relationship
   actually produced (check-ins, tasks, roadmaps, life-tracking entries once Phase 6
   ships) — never fabricated, never inferred without a source row.
4. **LLM Interpretation** — renders, explains, and converses using only what layers
   1–3 hand it. It never performs an authoritative calculation (ADR 003, extended by
   ADR 011 for V2's relationship/evidence surfaces).

## Grounding principle

> Numerology provides context. User data provides evidence. Deterministic/statistical
> services calculate. The LLM interprets and renders.
>
> **NO EVIDENCE → NO CLAIM.**

This principle is the acceptance bar for every V2 feature spec in this directory: any
claim shown to a user must be traceable to a canon value, a knowledge entry, or a
workspace evidence row — never to LLM invention alone.

## Relationship to NUMRA V1

AVENYTH V2 is built **additively** on the existing NUMRA V1.6 platform (deterministic
canon, golden fixtures, FastAPI + PostgreSQL, server-side sessions, reports, LLM
abstraction, PWA, Today/Timing, Relationships V1, RBAC/Admin, PDF, CI, Docker,
production deployment). See `specs/v2/architecture.md` for what changes and what is
explicitly frozen.

## Out of scope for V2 Core

- Native mobile apps (Section 39 — after V2 Core acceptance).
- Life Tracking / Evidence Layer (Section 34 / `specs/v2/evidence-policy.md` — after
  Relationship Core, Phase 6).
- Real payment/billing integration (entitlements ship now; billing later,
  `specs/v2/api-contract.md`).
- Any relationship compatibility percentage or match score
  (`specs/v2/relationship-type-spec.md`).
