# AVENYTH PWA — Canonical Execution State

- **PLAN_VERSION:** 5
- **STATUS_DATE:** 2026-09-20
- **CANONICAL_CLIENT:** responsive web application / installable PWA (`apps/web`)
- **NATIVE_MOBILE:** frozen; historical MOBILE-12A/B/C code remains, no new feature work
- **VERIFIED_MAIN_SHA:** `fa869f6ec4b66940dec9278af1a34d452f6af3aa` (PR #158 — der letzte verhaltensändernde Merge: der
  sichere Dependency-Batch; die Closure-Kette davor, #156, war test-only und ist deshalb kein
  neuer Baseline-Kandidat, sondern im Delivery-Map-Eintrag unten vermerkt)
- **VERIFIED_PRODUCTION_SHA:** `b0ff3380be1765a1b438283cfdad4656c9890d73` (no auto-deploy on this host — deliberately not advanced since the migration)
- **LAST_MERGED_PR:** [#158](https://github.com/GoLukeEnviro/numra-v1/pull/158)
- **LAST_GREEN_MAIN_RUN:** post-merge run on `fa869f6e` (12/12 jobs green, run `35528510287`)
- **CURRENT_MILESTONE:** PWA Product Closure
- **CURRENT_TASK:** PWA-06 — the audit stack still runs the mock provider, so the real-provider acceptance (relationship analysis, shadow dynamics, QUICK/FULL/ULTIMATE reports, workspace Copilot, PDF) has not been demonstrated in the acceptance environment; the Personal Copilot surface does not exist (#123). PWA-05 waits on an external mail provider (see its roadmap row). The 2026-09-20 closure chain (#146, #152, #154, #155, #156) and the branch/dependency hygiene pass are landed — see the delivery map. **Open internal product blocker: the Personal Copilot surface does not exist (#123)** — that is a repository-side gap, not an external one. Open external acceptances: a real LLM provider (#124/#139) and SMTP (#121).
- **NEXT_ACTION:** Work order as agreed on 2026-09-20: **(1)** this state reconciliation; **(2)** the SAST CI gate and hardening proof **#140** (`workflow` scope, own job, `sast` added to branch protection); **(3)** the **Personal Copilot #123** (API, context, UI, isolation, E2E) — not in parallel with SMTP; **(4)** deploy the **audit** stack to the then-current SHA and run the real-provider acceptance (relationship, shadow dynamics, QUICK/FULL/ULTIMATE, copilot, DOM/DB/PDF/export), closing #124/#139; **(5)** production capability (analysis worker, provider, feature flags, backup/rollback/smoke); **(6)** SMTP last: compose wiring, provider, DNS, real mailbox, verify/reset E2E, closing #121; **(7)** PWA-10 (accessibility, performance, install/offline/update, final production smoke, audit teardown, closure document). Audit records stay untouched: only PWA-10 authorizes teardown and deletion. Deliberately non-blocking follow-ups opened by the hygiene pass: the major upgrades #159 (Tailwind 4), #160 (Express 5), #161 (ESLint 10), #162 (React 19) and #163 (pytest constraint), plus #164 (vitest 5.0.1 breaks the jest-dom type augmentation) and #165 (decide how `apps/mobile` gets CI coverage).
- **OPEN_RELEASE_BLOCKERS:** **not none.** Production itself is untouched and unreleased, but the closure is held by: the missing Personal Copilot (#123), the outstanding real-provider acceptance (#124/#139), the external SMTP dependency (#121) and the still-open PWA-10 gate. **Corrected 2026-09-20:** the former wording claimed the audit instance had code parity to `main`; a file-level comparison against the running `numra-audit-api-1` container shows it does **not** — the container's sources predate 2026-09-20T00:09Z (`pipeline.py` still matches the 2026-08-24 revision, `export_service.py` the 2026-08-20 one, `pyproject.toml` the 2026-09-14 one, `uv.lock` the 2026-09-15 one) and therefore miss the mock-prompt-leak pipeline fix, the whole closure chain (#146/#152/#154/#155/#156) and the dependency batch (#158). Parity is restored deliberately in step (4) above — by deploying the audit stack to the then-current SHA before the acceptance.

This file is the single current execution-state source. Historical plans and gap
reports remain in the repository as evidence, but do not override this state.

## Baseline semantics (read before updating the fields above)

The **product baseline** is the last fully tested, behaviour-changing merge — not the
last merge of any kind. Concretely:

- `VERIFIED_MAIN_SHA` names the last behaviour-changing merge that passed the full CI
  set. A pure closure/documentation PR does **not** become a new product baseline and
  must not be written into that field; it is recorded in the delivery map instead.
- `LAST_MERGED_PR` names that same behaviour-changing PR, and `LAST_GREEN_MAIN_RUN`
  its post-merge run — so the three fields always describe one consistent revision.
- This is stated explicitly so a later parser or reviewer does not misread a
  deliberately-not-advanced field as staleness. Renaming these fields is out of scope:
  unknown readers may depend on the current names.

For PWA-04 this means: baseline `665d4447` (PR #116). PR #118 is the closure
documentation that records it, not a baseline of its own.

## Current product position

The V2 relationship core described by `PR-V2-00` through `PR-V2-11` is implemented.
Roadmaps, shared reflections, private/shared Copilot, dissolution/privacy closure and
the evidence layer are no longer future work. The supported product client is the
responsive web/PWA. Native MOBILE-12A/B/C was completed, then deliberately frozen.

The isolated PWA-01 audit exercised two synthetic accounts and dense states through
normal product flows. It found one user-facing mock-provider prompt-disclosure defect.
PR #98 fixed that defect, all required CI checks passed, and the same revision was
deployed and smoke-tested in production. The isolated audit environment and synthetic
records are intentionally retained until Product Closure.

## Completed delivery map

| Delivery area | State | Evidence |
|---|---|---|
| V1.5 / V1.6 platform | complete and live | `docs/adr/007-v1-5-product-completion.md`, `docs/releases/v1.6-b.md` |
| V2 PR-V2-00–07 | complete | ADR/spec history and WEB-01–07 planning evidence |
| PR-V2-08 Roadmaps + Shared Reflection | complete | PR #59, `docs/planning/web08-release-basis.md` |
| PR-V2-09 Relationship Copilot | complete | PR #75 |
| PR-V2-10 Dissolution + Privacy Closure | complete | PR #77 |
| PR-V2-11 Evidence Layer | complete | PR #76 |
| MOBILE-12A/B/C | complete, then frozen | PRs #78, #79, #84; `docs/releases/mobile-12c.md` |
| Workspace-hub route/card repair | complete | PR #87 |
| PWA-01 isolated dense-state audit | complete | `docs/audits/2026-09-15-pwa-01-isolated-audit.md` |
| Mock Copilot disclosure regression | fixed and deployed | PR #98, main SHA above |
| PWA-04 two-account acceptance + finding chain | complete | `docs/audits/2026-09-18-pwa-04-automated-two-account.md`; PRs #111, #112, #113, #114, #116 |
| Closure chain #134/#135/#136/#137/#145/#146/#152/#154/#155/#156 | complete | PRs #146, #152, #154, #155 and the test-only #156 (merge `2a8899d`, post-merge `main` 20 checks green) |
| Branch + dependency hygiene 2026-09-20 | complete | `docs/audits/2026-09-20-branch-hygiene.md`; 37 → 1 remote branch, safe dependency batch PR #158 (`fa869f6`), seven follow-up issues #159–#165 |

## Evidence boundary

### Verified

- PR #98 and the post-merge `main` run completed all 12 required CI checks.
- PWA-04 closed on `665d4447`: post-merge `main` run `35477414287` finished 12/12 jobs green.
- The PWA-04 acceptance suite ran unattended on the merge commit — `scripts/rc2-e2e.sh audit`,
  4 passed on desktop 1440x900 and mobile 390x844, exit 0, with the 06c/07a evidence
  screenshots regenerated.
- The mock-report leak is closed at the source: QUICK/FULL/ULTIMATE generation shows
  0 bracketed markers and 0 instruction-prose hits, and freshly persisted
  `report_sections.content_json` rows (14/14) carry neither.
- Production and audit API readiness covered database, calculation engine, LLM and PDF.
- The audit exercised sign-up, people, connections, consent, relationship workspace,
  tasks, roadmaps, milestones, shared reflection, check-in and shared Copilot flows.
- A real production Ollama/DeepSeek request returned HTTP 200 without personal data;
  `docs/releases/mobile-12c.md` records the controlled smoke.
- Dependabot is configured and actively producing pull requests.
- Production backup/update automation exists and has been exercised during release.

### Not yet a closure claim

- PWA-01 used an isolated production-like stack, not a destructive test against real
  production user data.
- Email verification/reset was not completed with controlled deliverable inboxes.
- Personal Copilot and paid/external report/PDF generation were left in empty state.
- Dynamics remained empty because a separate relationship-analysis generation was not run.
- The current production values of every V2 feature flag have not yet been captured in a
  sanitized, versioned inventory.
- Monitoring/alerting, CSP hardening, restore rehearsal and versioned production topology
  remain engineering/operations work, not reasons to reopen completed product features.
- GitHub currently reports one moderate Dependabot security alert on the default branch;
  its affected package and runtime relevance still require explicit triage.

## Product Closure roadmap

| ID | Outcome / exit gate | State |
|---|---|---|
| PWA-01 | Isolated dense-state, two-account audit; defects recorded and fixed | **complete** |
| PWA-02 | Current documentation agrees on scope, completion and next action | **complete, re-synced 2026-09-19** — the host migration and the PWA-04 finding chain had made the audit-host references stale; `docs/ops/2026-09-19-hermestrader-to-agent0-migration.md` and the cross-environment table in `docs/audits/2026-09-15-pwa-01-isolated-audit.md` now carry the current host, and `NEXT_ACTION` above reflects the real state |
| PWA-03 | Sanitized production flag/topology inventory and route/API parity smoke | **complete** |
| PWA-04 | Controlled two-account relationship acceptance, including analysis, consent changes and dissolution history | **complete, closed 2026-09-20** — the suite runs unattended (`scripts/rc2-e2e.sh audit`, 4 passed desktop+mobile) and the 2026-09-19 review findings are merged: #111 off-origin guard, #112 pipeline prompt-leak fix, #113 inventory/audit-doc sync, #114 E2E assertion hardening + Redis reset + register rate-limit test, #116 unbracketed instruction prose + `await` fix |
| PWA-05 | Controlled email lifecycle: verify, resend, forgot/reset and anti-enumeration | **in progress, blocked on an external provider** — reality check done and all four contracts proven by execution (single use, expiry, tamper, anti-enumeration with identical headers, e-mail normalisation, rate limits); two findings closed (re-verification no longer moves `email_verified_at`, #119; the log backend no longer prints the recovery token, #122); the real transport path is proven end to end against a loopback SMTP sink (`DELIVERY_PROOF_OK`). Not complete: no SMTP provider, sender domain or controlled mailbox exists in any environment, so the external delivery proof is outstanding (#121) |
| PWA-06 | Personal Copilot, real-provider report generation and PDF acceptance | **blocked** — no LLM provider is configured in the acceptance environment (the audit stack deliberately runs `mock` for deterministic replies; see #124). The Personal Copilot does not exist as a product surface at all: no non-workspace-scoped route accepts a thread, and `PERSONAL_PRIVATE` raises `NotFoundError` (#123) |
| PWA-07 | Privacy/evidence acceptance: export, account deletion, cascade and cleanup proof | **complete** — the retention/cascade matrix is documented and enforced (`docs/audits/2026-09-20-pwa-07-retention-matrix.md` plus `test_account_deletion_cascade_matrix.py`, merged as #131), and the missing account data export now exists: `GET /v1/account/export` delivers a versioned, streamed JSON document with every documented category, reachable from `/settings/privacy`, proven cross-account-safe and free of credentials/prompt material by 14 integration tests plus a web component test (`docs/audits/2026-09-20-pwa-07-account-export.md`). The former `ExportType.JSON` path is gone: #152 (merged `0093dfe`) removed the unreachable JSON report export and rejects unknown export types with 422, with OpenAPI schema and TS client regenerated by the drift gate |
| PWA-08 | Security/test hardening: triage current alert, CSP, SAST and targeted frontend coverage | **in progress** — HSTS was missing on both live surfaces and the security headers were untested; both fixed and pinned by tests (#126, merged as #127). The dependency alert is triaged as unreachable (#128, closed 2026-09-20). The `ALLOW_SELF_SIGNUP` product decision is **closed** (#115, closed 2026-09-20T08:04Z). Open from this phase: the SAST gate in CI plus the hardening proof (#140) |
| PWA-09 | Operations: monitoring, sanitized versioned deployment topology and restore drill | **complete** — monitoring/readiness probe, sanitized topology and restore drill (#148, merged 2026-09-20T07:53Z) plus job-failure alarm semantics, unreadable-probe handling and the removable audit probe (#151, merged 2026-09-20T15:35Z); an external pager remains a documented operational boundary, not a closure gap |
| PWA-10 | Final desktop/mobile-PWA regression, accessibility/performance/install checks, closure decision and audit teardown | queued |

## Priority and sequencing rules

1. Finish PWA-02 before creating more feature work; conflicting status documents are an
   execution risk.
2. PWA-03 is read-only first. It must not print secrets, tokens, cookies or credentials.
3. PWA-04–07 use only dedicated synthetic accounts and normal product flows.
4. PWA-08 and PWA-09 can proceed independently once PWA-03 establishes the deployed
   boundary, but neither may silently change product semantics.
5. PWA-10 is the only gate that authorizes deletion of audit records and retirement of
   the isolated audit stack.
6. Dependabot PRs are a maintenance lane. Minor/patch updates may be batched only after
   their CI is green; major updates require separate migration review and are not Product
   Closure blockers unless a supported dependency is insecure or broken.

## Explicit non-goals

- Do not restart native-mobile feature development.
- Do not implement astrology without a frozen canon/spec and a separate product decision.
- Do not use personal production accounts or real relationship/journal data for acceptance.
- Do not expose secrets in documentation, screenshots, CI output or audit artifacts.
- Do not treat historical unchecked checklists as evidence that completed features are open.
