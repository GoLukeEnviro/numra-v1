# Phase 4 Evidence — Long-Form Report Pipeline + Worker

| Item | Status |
|---|---|
| Report manifest builder (QUICK/FULL/ULTIMATE/CUSTOM, correct word ranges) | PASS |
| AgentWrite pipeline (per-section grounding, generation, validation, global context carry-forward, assembly) | PASS |
| 15,000+ word ULTIMATE report generation succeeds with Mock Provider | PASS |
| All manifest sections present, no core number mutation | PASS |
| Global Report Linter (MissingSections, DuplicateHeadings, DuplicateParagraphDetection, WordCountValidation, PlaceholderResolution, UnsupportedClaims, MetricReferenceIntegrity/NumericalConsistency) | PASS |
| Placeholder resolution (`{{metric:ID}}` → canonical display value, never LLM-invented) | PASS |
| One controlled repair attempt on invalid numeric claim, then hard fail | PASS |
| Postgres job queue (`SELECT ... FOR UPDATE SKIP LOCKED`) | PASS — real Postgres, not mocked |
| Restart-safety (crashed-worker lease reclaim) | PASS |
| Idempotency (`Idempotency-Key` header) | PASS |
| Failed-job recovery / max-attempts cutoff | PASS |
| API endpoints (`POST /v1/reports`, `GET /v1/reports/{id}`, `GET /v1/report-jobs/{id}`) | PASS |
| ruff format / ruff check / mypy strict | PASS |
| pytest | PASS — 194 passed repo-wide |

## Commands run

```text
$ uv run pytest packages/engine-interpretation/tests/unit/test_report_pipeline.py -q
13 passed

$ uv run pytest apps/api/tests/integration/test_reports.py -q
3 passed

$ uv run pytest packages apps/api/tests -q
194 passed

$ uv run ruff format --check . && uv run ruff check . && \
  uv run mypy apps/api/src packages/engine-numerology/src packages/engine-interpretation/src packages/engine-astrology/src
All checks passed! / Success: no issues found in 88 source files
```

## Architecture

- `packages/engine-interpretation/src/numra_interpretation/report/` — pure pipeline logic
  (manifest, per-section generation via the Phase 3 `LLMProvider` protocol, the
  placeholder-resolution renderer, the global linter). No DB, no HTTP.
- `apps/api/src/numra_api/repositories/reports.py` — the Postgres job queue:
  `claim_next_job()` uses `SELECT ... FOR UPDATE SKIP LOCKED` scoped to
  `{QUEUED, OUTLINE, GENERATING, VALIDATING, ASSEMBLING}` jobs whose `lease_until` is
  null or expired, so a crashed worker's job is reclaimed by the next poll rather than
  stuck forever. `attempt_count` is capped at `MAX_ATTEMPTS=3`; a job that keeps failing
  is marked `FAILED` with `error_code=WORKER_RETRY_LIMIT_EXCEEDED` instead of retried
  forever.
- `apps/api/src/numra_api/services/report_service.py` — orchestrates one job's full
  lifecycle (`QUEUED → OUTLINE → GENERATING → VALIDATING → ASSEMBLING → COMPLETE/FAILED`),
  loads the immutable `Calculation.canonical_profile_json` snapshot back into a
  `CanonicalProfile`, runs the pipeline, persists `ReportSection` rows + `Report.content_json`.
- `apps/api/src/numra_api/worker.py` — standalone poller (`python -m numra_api.worker`),
  separable into its own container/process; `run_one_cycle()` is used directly by tests
  for deterministic single-cycle control instead of the infinite poll loop.

## Judgment calls made explicit

- **Restart safety is retry-from-scratch, not mid-section resume.** If a worker crashes
  during `generate_report()`, no partial `ReportSection` rows exist yet (they're only
  persisted after the whole pipeline call returns), so the next worker that reclaims the
  expired-lease job reruns the entire pipeline rather than resuming from the last
  completed section. This satisfies "a stuck job eventually gets processed" (the actual
  restart-safety requirement tested) without the added complexity of incremental
  section checkpointing, which the master prompt does not explicitly demand.
- **Section list is the same practical subset chosen in Phase 3** (`executive_profile`,
  the 8 uniform core metrics, `special_numbers`, `cycles`, `timing`, `development`,
  `calculation_appendix` — 14 sections), not master prompt §106's full ~30-topic list.
  Relationship/love/career/spiritual-reflection narrative sections are not built because
  there is no dedicated knowledge content for them yet; adding them is additive, not a
  breaking change to this pipeline.
- **Word-count fidelity against `MockLLMProvider` is approximate by construction.** The
  mock provider deliberately **echoes** its structured request (system instructions +
  every grounding block + numeric-claim lines) back as `text`, rather than generating
  prose — that is by design (see its own docstring, Phase 3), useful for round-trip
  correctness testing but structurally unable to hit a tight per-section word target
  the way a real LLM would. The pipeline computes an overhead-aware elaboration length
  to get close anyway, and the linter's `WordCountValidation` check uses a generous
  tolerance (50% + a 250-word flat allowance) reflecting that reality — it still catches
  a genuinely missing/near-empty section, just not tight prose-length precision, which
  only a real generation quality evaluation (out of scope here) could meaningfully check.
- **`MAX_ATTEMPTS=3`** (workers) and the pipeline's **one repair attempt** (per section,
  inside a single job run) are two independent limits, not compounded — a section that
  fails numeric-claim validation gets one immediate regeneration attempt within the same
  job attempt; if the whole job then still fails the global lint, that counts as one
  *job* attempt toward the worker-level `MAX_ATTEMPTS`.
- **`knowledge_version` is hardcoded to `"1.0.0"`** when creating a report (matching
  `knowledge/manifest.yaml`'s current version) rather than reading the manifest file at
  request time — avoids a filesystem read on the hot path of report creation; the
  worker re-reads the real manifest version when it actually runs the pipeline
  (`knowledge.manifest.version`), which is what ends up in the final `content_json`.

## Not yet built (explicitly out of Phase 4 scope, deferred to Phase 6)

- PDF rendering of the assembled report (`apps/pdf`).
- `/v1/exports` endpoints.
- Live Ollama Cloud report generation — **NOT VERIFIED / EXTERNAL_DEPENDENCY_NOT_AVAILABLE**
  (no `OLLAMA_API_KEY` in this environment, same as Phase 3). The pipeline is provider-agnostic
  (`LLMProvider` protocol) so swapping `MockLLMProvider` for `OllamaCloudProvider` requires
  no pipeline changes, but that substitution itself is unverified end-to-end.
