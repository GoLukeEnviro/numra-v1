# ADR 004 — Postgres-Backed Report Job Queue, Not In-Request Generation

## Status

Accepted.

## Context

An ULTIMATE report targets 15,000-30,000 words across ~14 sections, each a separate
LLM call. That cannot happen inside a single synchronous HTTP request without risking
gateway timeouts, and FastAPI's `BackgroundTasks` doesn't survive a process restart —
an in-flight report would simply vanish if the API pod recycled mid-generation.

## Decision

Report generation is a first-class, persisted job: `report_jobs` is a Postgres table
with `status`, `progress`, `attempt_count`, `locked_at`, `lease_until`. A standalone
worker process (`numra_api.worker`, its own Docker service/container) claims work with

```sql
SELECT ... FROM report_jobs
WHERE status IN (QUEUED, OUTLINE, GENERATING, VALIDATING, ASSEMBLING)
  AND (lease_until IS NULL OR lease_until < now())
ORDER BY created_at
FOR UPDATE SKIP LOCKED
LIMIT 1
```

so multiple worker replicas can run concurrently without ever double-processing a job,
and a crashed worker's job (lease expired, no completion) is reclaimed by the next
poll rather than stuck forever. `POST /v1/reports` accepts an `Idempotency-Key` header
so a client's duplicate submit (double-click, retried request) returns the existing
job instead of paying for generation twice.

## Consequences

- The API layer stays fast and stateless for report creation (`POST /v1/reports`
  returns immediately with status `PENDING`); polling `GET /v1/report-jobs/{id}` is the
  client's job-progress mechanism.
- Horizontal scaling of report generation is "run more worker replicas," with no
  coordination needed beyond the database itself.
- Restart-safety is retry-from-scratch per job (see specs/evidence/phase-4.md), not
  mid-section resume — a deliberate scope cut given the added complexity incremental
  checkpointing would need, weighed against "a stuck job eventually completes" being
  the actual requirement.

## Update — retry/backoff correctness (production hardening pass)

The original implementation had a real bug: a retryable failure was marked `FAILED`
even when `attempt_count < MAX_ATTEMPTS` — `FAILED` was never in the reclaimable
status set above, so a job that failed once could never actually be retried despite
`MAX_ATTEMPTS=3` existing in the code. `report_jobs` gained a `next_attempt_at` column
and `claim_next_job`'s query above gained an additional
`AND (next_attempt_at IS NULL OR next_attempt_at <= now())` clause; a retryable
failure now goes back to `QUEUED` with an exponentially increasing `next_attempt_at`
(`requeue_job_for_retry`) instead of `FAILED`, and `FAILED` is now reserved for a
non-retryable failure or one where `attempt_count` has actually been exhausted
(`fail_job_terminally`). See `apps/api/tests/integration/test_report_retry.py` for the
retry-state-machine test coverage this added.
