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
