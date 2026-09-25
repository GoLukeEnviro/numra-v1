# AVENYTH Product Closure — Documentation and Roadmap Review

**Review date:** 2026-09-16  
**Repository basis:** `main` at `c388456a3b9b734d29e68fef4001dd70c9318f6d`  
**Scope:** all 78 Markdown documents in the repository plus current GitHub PR/CI state  
**Canonical current state:** `docs/planning/avenyth-pwa-execution-state.md`

## Executive conclusion

The application is not at “PR-V2-08 next” anymore. The V2 web relationship feature set
through Evidence Layer and Privacy Closure is implemented. Native mobile reached a small
read-only milestone and is now intentionally frozen in favor of the PWA. PWA-01 completed
an isolated two-account production-like audit, its only newly found disclosure defect was
fixed in PR #98, and that revision is merged, green and deployed.

The project is therefore in **Product Closure**, not core feature construction. The next
work should close acceptance, security and operations evidence without reopening completed
features.

## Documentation inventory

| Area | Files | Role | Assessment |
|---|---:|---|---|
| `docs/` | 42 | ADRs, planning, audits, releases, analysis, runbooks | Strong evidence base; current state was fragmented |
| `specs/` | 30 | canon, V2 contracts, phase evidence | Binding scope/contract; some status labels are historical |
| `knowledge/` | 2 | interpretation-content documentation | Domain support |
| root / `plans/` / `apps/` | 4 | entry points and overview | old project overview was materially stale |

The review preserves historical evidence. It adds a canonical current-state document and
marks superseded analyses as snapshots instead of rewriting their original conclusions.

## Reconciled facts

| Earlier statement | Current fact | Disposition |
|---|---|---|
| WEB-07 complete; PR-V2-08 next | PR-V2-08–11 are complete | superseded |
| MOBILE-12C / Dependabot #70 and #80 next | MOBILE-12C is complete/frozen; #70/#80 merged | superseded |
| Live LLM unverified | controlled production Ollama/DeepSeek request succeeded | resolved for smoke scope |
| No Dependabot | Dependabot is active; nine update PRs are open | resolved; maintenance remains |
| Backup automation absent/unverified | backup/update automation exists and was used during release | partially resolved; restore rehearsal remains |
| Astrologie is a critical release blocker | feature is deliberately disabled without canon | not a PWA Product Closure blocker |
| Native mobile is the next product surface | product decision freezes native and makes PWA canonical | superseded |

## What is actually finished

- Deterministic numerology and interpretation foundation, auth, people and reports.
- V2 personal/relationship workspaces, connection and consent flows.
- Relationship/shadow interpretation, configurable check-ins and shared tasks.
- Roadmaps, milestones and shared reflections.
- Private/shared Copilot, Evidence Layer, dissolution and privacy closure.
- Responsive web surface and installable PWA foundation.
- Automated 12-check CI, dependency auditing, Docker/system E2E coverage.
- Controlled production LLM smoke and production health checks.
- Isolated dense-state two-account PWA-01 audit and regression fix from that audit.

## Remaining product evidence

1. Capture production feature-flag/topology parity without secrets.
2. Generate relationship analysis and verify the complete consent/revoke/regrant and
   dissolution lifecycle with dedicated accounts.
3. Exercise deliverable email verification and password-reset flows.
4. Exercise personal Copilot, real report generation and PDF download.
5. Exercise export/account deletion/cascade cleanup with evidence.
6. Run final PWA install/offline/update, responsive, accessibility and performance checks.

## Remaining engineering and operations work

- Replace permissive CSP behavior with a nonce/hash-based policy where compatible.
- Add SAST/security scanning beyond dependency audits.
- Triage the one moderate Dependabot security alert currently reported on the default
  branch and prove whether the affected dependency is shipped/runtime-reachable.
- Measure and close targeted frontend coverage gaps rather than relying on old counts.
- Version a sanitized production topology/template while keeping secrets external.
- Add monitoring/alerting and perform a documented backup restore drill.
- Triage open Dependabot PRs: minor/patch first; major framework/tool migrations separately.

## Open maintenance pull requests

At review time, PRs #89–#97 are Dependabot updates. They are not missing product features.
PRs for pytest, Tailwind, Express and ESLint include major-version changes and require
focused migration review. GitHub reports one moderate Dependabot security alert on the
default branch; it is not yet triaged. No open GitHub issues were found.

## Documentation decisions

- `docs/planning/avenyth-pwa-execution-state.md` is authoritative for current execution.
- `docs/planning/avenyth-web-execution-state.md` is retained as detailed delivery history.
- `plans/projektueberblick.md`, `docs/analyze/gap-analyse.md`,
  `docs/analyze/technical-debt.md`, `docs/analyze/gap-bericht-2026-09-11.md`,
  `docs/analyze/gap-verification-2026-09-11.md` and `FINAL_VERIFICATION.md` are historical
  snapshots.
- `specs/v2/product-vision.md` remains the frozen scope source; its “Draft — Phase 0” label
  does not represent delivery status.
- `.specify/feature-012c-mobile-today-brief/` is completed historical acceptance evidence.

## Recommended next action

Execute PWA-03 as a read-only production parity audit, publish a sanitized inventory, and
turn any mismatch into a focused PR. Do not add more synthetic content until the deployed
feature boundary is known. The executable sequence is in
`docs/plans/2026-09-16-pwa-product-closure.md`.
