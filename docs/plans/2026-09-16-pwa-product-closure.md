# AVENYTH PWA Product Closure Implementation Plan

> **For Claude:** Use `${SUPERPOWERS_SKILLS_ROOT}/skills/collaboration/executing-plans/SKILL.md` to implement this plan task-by-task.

**Goal:** Produce enough product, security and operations evidence to make a deliberate PWA release-closure decision, then remove the isolated audit environment safely.

**Architecture:** Keep the deterministic engines and existing Next.js/FastAPI/Postgres stack unchanged. Validate through public product contracts and normal UI flows, add narrowly scoped regression tests for defects, and store only sanitized evidence. Production observation is read-only unless a reviewed PR and controlled deployment are explicitly part of a task.

**Tech Stack:** Next.js/React/TypeScript, FastAPI/Python, PostgreSQL, Playwright, Vitest, pytest, Docker Compose, GitHub Actions, Tailscale Serve.

---

## Task 1: Complete PWA-02 documentation reconciliation

**Files:**
- Create: `docs/planning/avenyth-pwa-execution-state.md`
- Create: `docs/analyze/product-closure-overview-2026-09-16.md`
- Modify: `docs/planning/avenyth-web-execution-state.md`
- Modify: `plans/projektueberblick.md`
- Modify: `docs/analyze/gap-analyse.md`
- Modify: `docs/analyze/technical-debt.md`
- Modify: `docs/analyze/gap-bericht-2026-09-11.md`
- Modify: `docs/analyze/gap-verification-2026-09-11.md`
- Modify: `.specify/feature-012c-mobile-today-brief/spec.md`
- Modify: `.specify/feature-012c-mobile-today-brief/tasks.md`

**Step 1: Prove the repository/CI basis**

Run:

```bash
git rev-parse origin/main
gh pr view 98 --json state,mergedAt,mergeCommit,statusCheckRollup,url
gh run list --branch main --limit 1 --json headSha,status,conclusion,url
```

Expected: SHA `c388456a...`, PR #98 merged, latest `main` run successful.

**Step 2: Verify current-state references**

Run:

```bash
rg -n "PR-V2-08.*(next|nächster|offen)|LIVE_LLM_SMOKE = NOT_VERIFIED|Kein Renovate/Dependabot" docs plans
```

Expected: remaining matches appear only inside explicitly marked historical snapshots or
quoted reconciliation tables.

**Step 3: Check Markdown links and the diff**

Run the repository link checker if one exists; otherwise resolve local Markdown links with
fragment and `:line` suffixes removed and allow documented repository-root-relative links.

Expected: no new broken local links. `git diff --check` exits 0.

**Step 4: Commit**

```bash
git add docs plans .specify/feature-012c-mobile-today-brief
git commit -m "docs: define PWA product closure roadmap"
```

## Task 2: PWA-03 production parity inventory

**Files:**
- Create: `docs/audits/YYYY-MM-DD-pwa-03-production-parity.md`
- Modify if mismatched: `.env.example`
- Modify if mismatched: `docs/runbooks/deployment.md` or the closest existing deployment runbook

**Step 1: Define a secret-safe assertion list**

Record only expected names and boolean/public values for:

```text
AVENYTH_V2_ENABLED
AVENYTH_CONNECTIONS_ENABLED
AVENYTH_RELATIONSHIP_WORKSPACES_ENABLED
AVENYTH_CHECKINS_ENABLED
AVENYTH_TASKS_ENABLED
AVENYTH_COPILOT_ENABLED
AVENYTH_EVIDENCE_LAYER_ENABLED
```

Never print environment files wholesale.

**Step 2: Read deployed identity and health**

Verify repository HEAD, deployed SHA, container health, migrations and public readiness.
Expected: production matches reviewed `main`; database, engine, LLM and PDF are healthy.

**Step 3: Run route/API parity smoke**

Use an already authenticated dedicated audit session. Verify every navigation surface maps
to a supported API contract and no browser-console error occurs. Do not mutate unrelated
users or expose session material.

**Step 4: Publish sanitized evidence and branch on result**

If parity passes, mark PWA-03 complete. If it fails, write a failing regression test first,
implement the smallest fix, run the affected and full CI suites, and open a focused PR.

## Task 3: PWA-04 relationship lifecycle acceptance

**Files:**
- Create: `docs/audits/YYYY-MM-DD-pwa-04-relationship-lifecycle.md`
- Modify on defect: relevant `apps/web/**`, `apps/api/**`, or engine file
- Test on defect: colocated Vitest/pytest/Playwright regression

**Step 1: Reuse only the two run-tagged synthetic accounts**

Confirm account IDs and workspace ID against the PWA-01 inventory. Stop if identity cannot
be proven without reading credentials.

**Step 2: Exercise the full lifecycle**

Generate relationship analysis; verify private/shared boundaries; revoke and regrant
consent; verify proposals, check-in, Copilot and evidence behavior; dissolve and verify
read-only history and blocked mutations.

**Step 3: Capture sanitized assertions**

Record route, actor, expected status/state and actual result. Screenshots may contain only
synthetic data.

**Step 4: Apply TDD for every defect**

Write a failing test, observe the failure, implement the minimum correction, rerun focused
tests, then the 12 required CI checks through a PR.

## Task 4: PWA-05 controlled email lifecycle

**Files:**
- Create: `docs/audits/YYYY-MM-DD-pwa-05-email-lifecycle.md`
- Modify on defect: `apps/api/src/numra_api/routes/auth.py` and/or corresponding web UI
- Test on defect: auth route/component/E2E tests

Use two inboxes controlled by the owner. Verify sign-up verification, resend, expired/used
tokens, forgot/reset, post-reset login and generic anti-enumeration responses. Never record
passwords, tokens or message bodies containing secrets.

## Task 5: PWA-06 Copilot, report and PDF acceptance

**Files:**
- Create: `docs/audits/YYYY-MM-DD-pwa-06-report-copilot-pdf.md`
- Modify on defect: report/Copilot/PDF implementation and colocated tests

Use synthetic people only. Verify personal Copilot grounding, real-provider report job
completion, retries/failure presentation, report rendering and PDF download. Assert that
internal prompts, authorization material and unrelated user data are absent.

## Task 6: PWA-07 privacy and evidence acceptance

**Files:**
- Create: `docs/audits/YYYY-MM-DD-pwa-07-privacy-evidence.md`
- Modify on defect: privacy/evidence routes, repositories, UI and tests

Export one synthetic account, inspect the documented schema, delete it through the product,
and prove dependent personal/shared data is removed or retained exactly as specified. Use
database queries only as sanitized assertions, never as a shortcut around product behavior.

## Task 7: PWA-08 security and targeted test hardening

**Files:**
- Modify: `apps/web/next.config.*` and CSP middleware/config actually in use
- Modify: `.github/workflows/ci.yml`
- Create/modify: targeted frontend tests for gaps measured in this task
- Create: `docs/security/pwa-hardening.md` if no equivalent exists

First inspect the current moderate Dependabot alert without disclosing repository secrets;
record the affected package, reachability and remediation decision. Then add a failing header
assertion for the desired CSP and introduce nonce/hash handling without `unsafe-inline` where
compatible. Add a pinned SAST job. Measure frontend coverage and add tests only for high-risk
uncovered auth, consent, privacy and error-state branches.

## Task 8: PWA-09 operations closure

**Files:**
- Create: sanitized production Compose/template file in the existing deployment convention
- Create/modify: operations runbook and monitoring configuration
- Create: `docs/audits/YYYY-MM-DD-pwa-09-restore-drill.md`

Version topology without secrets, add service-level alerting for readiness/job failures, and
restore the latest backup into an isolated target. Assert migration level and selected row
counts/hashes; never overwrite production.

## Task 9: PWA-10 final closure and teardown

**Files:**
- Create: `docs/releases/pwa-product-closure.md`
- Modify: `docs/planning/avenyth-pwa-execution-state.md`
- Modify: `docs/audits/2026-09-15-pwa-01-isolated-audit.md`

Run the full required CI suite plus desktop/mobile-responsive journeys, accessibility,
performance, PWA install/update/offline-shell checks and production health smoke. Record a
go/no-go decision with residual risks. Only after a go decision, delete run-tagged synthetic
accounts, verify cascades, remove the isolated audit stack/volumes and audit-only Tailscale
mapping, then record the teardown result.
