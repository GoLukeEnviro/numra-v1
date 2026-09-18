# AVENYTH PWA — Canonical Execution State

- **PLAN_VERSION:** 5
- **STATUS_DATE:** 2026-09-18
- **CANONICAL_CLIENT:** responsive web application / installable PWA (`apps/web`)
- **NATIVE_MOBILE:** frozen; historical MOBILE-12A/B/C code remains, no new feature work
- **VERIFIED_MAIN_SHA:** `5c00d329826991b5de57f98d281c4732278d9807`
- **VERIFIED_PRODUCTION_SHA:** `b0ff3380be1765a1b438283cfdad4656c9890d73` (re-verify — the auto-deploy timer may have advanced this since last check)
- **LAST_MERGED_PR:** [#104](https://github.com/GoLukeEnviro/numra-v1/pull/104)
- **LAST_GREEN_MAIN_RUN:** post-merge run on `5c00d329` (12/12 required checks green on the PR head `dcf81d72`; see `docs/audits/2026-09-18-pwa-04-automated-two-account.md`)
- **CURRENT_MILESTONE:** PWA Product Closure
- **CURRENT_TASK:** PWA-04 — two-account relationship acceptance (automated path unblocked; see `docs/audits/2026-09-18-pwa-04-automated-two-account.md`)
- **NEXT_ACTION:** PWA-04 acceptance now runs unattended: `scripts/rc2-e2e.sh audit` locally, or the same suite against the remote audit instance via `RC2_BASE_URL=https://hermestrader.taile6801f.ts.net:8444 RC2_MSG_PREFIX=AUDIT npx playwright test --config=playwright.rc2.config.ts`. The manual-login blocker is resolved (non-prod stacks have ALLOW_SELF_SIGNUP=true and the journey self-registers its accounts). Next: PWA-05 email lifecycle, or a real-UI run of this suite against the audit instance.
- **OPEN_RELEASE_BLOCKERS:** none in production; numra-audit code parity with main verified directly (`RESOLVED_BY_DIRECT_CONTAINER_CODE_VERIFICATION`, see `docs/audits/2026-09-16-pwa-03-production-parity.md`); the former PWA-04 manual-login blocker is resolved by the automated two-account acceptance suite

This file is the single current execution-state source. Historical plans and gap
reports remain in the repository as evidence, but do not override this state.

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

## Evidence boundary

### Verified

- PR #98 and the post-merge `main` run completed all 12 required CI checks.
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
| PWA-02 | Current documentation agrees on scope, completion and next action | **complete** |
| PWA-03 | Sanitized production flag/topology inventory and route/API parity smoke | **complete** |
| PWA-04 | Controlled two-account relationship acceptance, including analysis, consent changes and dissolution history | **in progress** |
| PWA-05 | Controlled email lifecycle: verify, resend, forgot/reset and anti-enumeration | queued |
| PWA-06 | Personal Copilot, real-provider report generation and PDF acceptance | queued |
| PWA-07 | Privacy/evidence acceptance: export, account deletion, cascade and cleanup proof | queued |
| PWA-08 | Security/test hardening: triage current alert, CSP, SAST and targeted frontend coverage | queued |
| PWA-09 | Operations: monitoring, sanitized versioned deployment topology and restore drill | queued |
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
