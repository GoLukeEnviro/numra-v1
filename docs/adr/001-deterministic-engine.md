# ADR 001 — Deterministic, LLM-Free Numerology Core

## Status

Accepted.

## Context

Numerology results are the product this platform is built around. Users and any future
auditor need to be able to trust that a given birth name + birth date always produces
the same numbers, that every number is traceable back to an explicit formula, and that
no language model ever silently "helps" with the arithmetic.

## Decision

`packages/engine-numerology` is pure Python: no network import, no database import, no
LLM import, no global mutable state, no `random`, no `datetime.now()`/`date.today()`.
Every time-dependent calculation takes an explicit `as_of_date`. Every metric carries a
`CalculationTrace` with machine-truth operations (`letter_mapping`, `sum`, `reduce`
steps) — display strings are generated *from* the trace, never invented independently
of it. A repository test (`test_no_golden_leakage.py`) statically greps the package for
golden-fixture literals to keep this contract honest over time.

## Consequences

- Every layer above the engine (API, interpretation, LLM adapter, report pipeline, web,
  PDF) can treat a `CanonicalProfile` as ground truth and never needs to re-derive or
  double-check a numerological value — they only *read* it.
- Golden-reference testing (Lukas Springer) is meaningful: identical input always
  produces identical output, byte-for-byte (`to_canonical_json()`, `deterministic_hash`).
- Any future performance optimization (e.g. caching) is safe to key purely on
  `calculation_version` + normalized input, because there is no hidden state that could
  make two calls with the same input diverge.
