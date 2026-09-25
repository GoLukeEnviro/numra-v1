# AVENYTH PWA — Canonical Execution State

- **PLAN_VERSION:** 5
- **STATUS_DATE:** 2026-09-25 (3)
- **CANONICAL_CLIENT:** responsive web application / installable PWA (`apps/web`)
- **NATIVE_MOBILE:** frozen; historical MOBILE-12A/B/C code remains, no new feature work
- **VERIFIED_MAIN_SHA:** `dfeb8cdfd266900a36ab41aefc4e937aad7d7046` (PR #207 — the last behaviour-changing merge: the Wave 3 knowledge-migration closure, metrics `semantic_context_de` enrichment + tonality-pass fix + ADR 015 in `Proposed`, full CI set green). PR #208 (ADR 015 acceptance, Option A) is docs-only per the baseline semantics below and does not advance this field.
- **VERIFIED_PRODUCTION_SHA:** `f522067e8521d78335b3a4c3ec75739809ce1a32` — read from `/var/lib/numra/deployed_sha` on the host 2026-09-22, which is the authoritative source. **Corrected:** this field previously named `b0ff3380`, which is an *ancestor* of the deployed commit; production is 12 commits ahead of that value and 103 commits behind `main`. No auto-deploy on this host — production advances only by an explicit deploy. **Not re-verified in this 2026-09-25 pass** (not read from the host this session); production remains far behind `main`.
- **LAST_MERGED_PR:** [#207](https://github.com/GoLukeEnviro/numra-v1/pull/207)
- **LAST_GREEN_MAIN_RUN:** post-merge run on `dfeb8cd` (#207, [run 36108195346](https://github.com/GoLukeEnviro/numra-v1/actions/runs/36108195346), conclusion `success`)
- **CURRENT_MILESTONE:** PWA Product Closure
- **CURRENT_TASK:** **2026-09-25, Wave 3 knowledge-migration closure on `main`:** #201 (long-form schema + governance fields + Master-22 pilot + cookie-name/mobile-config fixes), #203 (numbers 1–9, masters 11/33, karmic debts long-form content + composer long-form-first), #204 (`AUTHORING_GUIDE.md` + 12 diagonal shadow-interaction rules), #205 (remaining 66 off-diagonal shadow-interaction rules — all 78/78 rules deepened), #206 (relationship-frames `number_modifiers` made relationship-type-specific, 230/576 de-duplicated), #207 (metrics `semantic_context_de` enrichment, a tonality-pass fix in `master-numbers/33.yaml`, and ADR 015 drafted as `Proposed`) are all merged. **ADR 015 (Element/Water system) accepted as Option A on 2026-09-25** (PR #208): `FEATURE_DISABLED_NO_CANON`, no interface, no spec, no knowledge content — see `docs/adr/015-element-water-system-open-decision.md` and `specs/canon-spec.md` §33. This closes the Wave-3/Phase-4 scope from the migration plan entirely. Unchanged from the prior entry below: the PWA-10 closure batch, Personal Copilot, and PWA-05 external-delivery work remain as previously verified on the host — this pass did not re-verify host-side state. **Open, out of scope for the Wave-3 closure:** #193 (production SMTP — the host composition mapping is done, an own relay key and an explicit deploy-go are pending), the operator gates (production deploy smoke, audit teardown), and #202 (CI-split, draft, behind `main` — needs a rebase and its required checks retargeted before it can merge).
- **NEXT_ACTION:** **(1)** Production SMTP: its own Resend key, the env write, and an explicit API-recreate go — not a silent full-`main` release; the composition-gap fix already landed on the host, this is the remaining key + deploy step for #193. **(2)** Rebase PR #202 onto current `main` and retarget its required checks (`engine-unit-property`, `api-integration`) before it can merge — a process blocker, not a release blocker. **(3)** Refresh this document again after those two steps. The prior PWA-10 work order (production deploy via `docs/ops/release-verification.md`, smoke, Go/No-Go, then operator-gated audit teardown) still applies underneath these two and is unchanged from the previous entry.
- **OPEN_RELEASE_BLOCKERS:** Unchanged in substance from the prior entry, carried forward: (1) **production SMTP** — the composition gap is closed on the host, but production's own relay key and an explicit deploy-go are still pending (#193); (2) the **operator gates** (production deploy smoke, audit teardown). `VERIFIED_PRODUCTION_SHA` was not re-read from the host this session and remains far behind `main`. **Not a release blocker but a process blocker:** PR #202 (CI-split) is a draft, behind `main`, and needs its required checks retargeted before merge — it does not gate any deploy on its own. **Corrected 2026-09-22:** `VERIFIED_PRODUCTION_SHA` no longer names `b0ff3380` but the host's actual `deployed_sha`; see the field above. **Corrected 2026-09-21:** the earlier wording (audit without code parity) is resolved — the audit stack runs parity to its deployed SHA, the real-provider acceptance ran against it, and the oracle distinction (`ollama_cloud` vs historical `mock-v1` rows) is documented in the acceptance evidence.

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
| Overnight run 2026-09-21 (nightrun, agent0) | complete | Scheduler proven (5 jobs, real timer runs); SAST required; audit stack + copilot live acceptance on 06cd97d; findings #172/#174/#176; evidence `nightrun/evidence/NU-REAL-PROVIDER-20260921.md` + `NL-SCHEDULER-PROOF.md` |
| PWA-08 SAST gate (#140) | complete and bound | PR #167 (merge `1d608c88`); `sast` job + required-check binding verified on the repo; hardening doc + frontend coverage in the same PR |
| Audit deploy + real-provider acceptance (#124/#139) | acceptance delivered for the covered surfaces | audit stack at `1d608c88`, parity 9/9; system journey green; relationship/shadow analyses attributed to `ollama_cloud`; evidence `nightrun/evidence/NU-REAL-PROVIDER-20260921.md`; failed-turn finding #174 |
| System-journey real-provider latency | fixed (test-only) | PR #175 — report wait sized for the real worker (60s → 600s), `1 passed (3.5m)` on the audit stack |
| LLM zero-retries edge case | fixed | issue #172, PR #173 — `NUMRA_LLM_MAX_RETRIES=0` now fails typed (found by the outage probe) |
| Personal Copilot API + UI slice (#123) | complete, closed | PR #170 (API, `9070ca3`) and PR #178 (UI on `/copilot`, `06cd97d`); re-accepted on the closure SHA `4b0926cd`: real-provider reply COMPLETE (382 chars, `ollama_cloud`), 422 on the name defect, cross-account 404, unauthenticated 401 — evidence `pwa06-reacceptance/PWA-06-REACCEPTANCE-20260921.md` |
| Closure batch 2026-09-21 (#176/#174) | complete | PR #182 `d055d48` (normalisation refusal → 422 domain error), PR #183 `126e2d8` (a FAILED copilot turn is visible, `role="alert"`, i18n), PR #184 `4b0926c` (the repair attempt receives the canonical values instead of the identical prompt); all three post-merge 16/16 green |
| PWA-10 checks (a11y/perf/install/offline) | measured; all three findings closed | `PWA10-CHECKS-20260921c.json`: a11y app desktop+mobile PASS, login desktop PASS, login mobile 1 violation; perf TTFB 17/14 ms; manifest+SW+icons 200; offline navigation deliberately network-only. Issues #185 (h1), #186 (offline decision), #187 (CORS allowlist/release checklist) |
| Wave 3 knowledge migration (#201–#207) | complete | PRs #201, #203, #204, #205, #206, #207 — long-form schema/governance fields + numbers/masters/karmic-debts content, `AUTHORING_GUIDE.md` + all 78 shadow-interaction rules, relationship-frames `number_modifiers` de-duplicated, metrics `semantic_context_de` enriched, tonality-pass fix |
| ADR 015 — Element/Water system | **Accepted, Option A** (`FEATURE_DISABLED_NO_CANON`) | `docs/adr/015-element-water-system-open-decision.md`; `specs/canon-spec.md` §33; PR #208 |

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

### Known boundaries (what this closure does not claim)

This section lists the limits that stay true after the 2026-09-22 closure. Statements
that were true earlier and are now resolved have been removed rather than kept as
stale hedges — the closure roadmap below is the authority on each phase.

- PWA-01 used an isolated production-like stack, not a destructive test against real
  production user data. That is a property of the audit method, not an open item.
- Email verification/reset **has** an external delivery proof, on the audit instance
  (2026-09-22): the audit stack sends through the real relay (`EMAIL_BACKEND=smtp`
  against `smtp.resend.com:587` with STARTTLS) and the delivered message carries the
  recipient's own verdicts (`spf=pass`, `dkim=pass header.i=@mail.avenyth.de
  header.s=resend`, `dmarc=pass`, `arc=pass`) — evidence in
  `docs/audits/2026-09-22-pwa-05-external-delivery.md`, issue #121 closed. The earlier
  wording that `avenyth.de` has no MX records described the state before the Cloudflare
  Email Routing setup and is no longer true: the domain now routes mail. **Production is
  a separate matter and does not yet have SMTP**: the production composition carries no
  `EMAIL_BACKEND`/`SMTP_*` mapping at all, so production cannot send even with a key on
  hand — tracked as an open gap, see the release-blocker note above.
- Offline navigation is deliberately network-only (ADR 014, #186): an offline reload of
  a page fails while the installable surface (manifest, service worker, precached
  static assets) still works. This is expected behaviour, not an acceptance failure.
- The production values of the seven V2 feature flags were captured in a sanitized,
  versioned inventory during PWA-03 (`docs/audits/2026-09-16-pwa-03-production-parity.md`)
  and all seven remain off in real production — intentional, not a defect.
- GitHub still shows the triaged `uuid` alert as open on the default branch. The
  triage (#128, closed 2026-09-20) established it is unreachable: the only path is
  `xcode@3.0.1` under `@expo/cli`, which is absent from both the web and the API
  production images. GitHub's alert state is therefore a bookkeeping difference, not
  a reachable risk.
- An external pager for monitoring remains a documented operational boundary
  (PWA-09); the readiness probe, job-failure alarm semantics and the removable audit
  probe are in place and tested.

## Product Closure roadmap

| ID | Outcome / exit gate | State |
|---|---|---|
| PWA-01 | Isolated dense-state, two-account audit; defects recorded and fixed | **complete** |
| PWA-02 | Current documentation agrees on scope, completion and next action | **complete, re-synced 2026-09-19** — the host migration and the PWA-04 finding chain had made the audit-host references stale; `docs/ops/2026-09-19-hermestrader-to-agent0-migration.md` and the cross-environment table in `docs/audits/2026-09-15-pwa-01-isolated-audit.md` now carry the current host, and `NEXT_ACTION` above reflects the real state |
| PWA-03 | Sanitized production flag/topology inventory and route/API parity smoke | **complete** |
| PWA-04 | Controlled two-account relationship acceptance, including analysis, consent changes and dissolution history | **complete, closed 2026-09-20** — the suite runs unattended (`scripts/rc2-e2e.sh audit`, 4 passed desktop+mobile) and the 2026-09-19 review findings are merged: #111 off-origin guard, #112 pipeline prompt-leak fix, #113 inventory/audit-doc sync, #114 E2E assertion hardening + Redis reset + register rate-limit test, #116 unbracketed instruction prose + `await` fix |
| PWA-05 | Controlled email lifecycle: verify, resend, forgot/reset and anti-enumeration | **complete, closed 2026-09-22** — the external delivery proof is delivered. The audit stack now sends through a real relay (`EMAIL_BACKEND=smtp` against `smtp.resend.com:587` with STARTTLS, `SmtpEmailSender` verified in the running app); the acceptance run `20260922T205442Z` returned `VERDICT=PASS` with an empty finding list, and the delivered message itself carries `spf=pass`, `dkim=pass header.i=@mail.avenyth.de header.s=resend`, `dmarc=pass` and `arc=pass`. Two mandate collisions were found and resolved, both documented in `docs/audits/2026-09-22-pwa-05-external-delivery.md`: Resend refuses `example.com` recipients (RFC 2606), so the account stays synthetic while delivery goes to the one controlled mailbox with a per-run plus-tag; and port 465 is unreachable from this network, so 587 with STARTTLS is used (2465 verified as fallback). The four contracts (single use, replay, tamper, expiry), anti-enumeration, the rate limit, hash-only token storage and the absence of secrets in any log were re-measured, not inherited. Production is untouched and still `disabled` |
| PWA-06 | Personal Copilot, real-provider report generation and PDF acceptance | **complete, closed 2026-09-21** — the provider is real (`NUMRA_LLM_PROVIDER=ollama`), the Personal Copilot exists and is accepted on the closure SHA (`4b0926cd`): thread `PERSONAL_PRIVATE` with `workspace_id=null`, reply `COMPLETE` 382 chars via `ollama_cloud`, persisted and re-readable, no prompt material in the stored text, cross-account 404, unauthenticated 401. Relationship/shadow/report surfaces keep their earlier real-provider evidence on `1d608c88` (untouched by the three fixes). #123/#124/#139 closed; the FAILED-turn path is test-covered, not live-forced — stated in the evidence |
| PWA-07 | Privacy/evidence acceptance: export, account deletion, cascade and cleanup proof | **complete** — the retention/cascade matrix is documented and enforced (`docs/audits/2026-09-20-pwa-07-retention-matrix.md` plus `test_account_deletion_cascade_matrix.py`, merged as #131), and the missing account data export now exists: `GET /v1/account/export` delivers a versioned, streamed JSON document with every documented category, reachable from `/settings/privacy`, proven cross-account-safe and free of credentials/prompt material by 14 integration tests plus a web component test (`docs/audits/2026-09-20-pwa-07-account-export.md`). The former `ExportType.JSON` path is gone: #152 (merged `0093dfe`) removed the unreachable JSON report export and rejects unknown export types with 422, with OpenAPI schema and TS client regenerated by the drift gate |
| PWA-08 | Security/test hardening: triage current alert, CSP, SAST and targeted frontend coverage | **complete, closed 2026-09-21** — HSTS and the security headers were fixed and pinned by tests (#126/#127); the dependency alert is triaged (#128); the `ALLOW_SELF_SIGNUP` decision is closed (#115); the SAST gate is merged **and bound** as a required check (#140 closed): own `sast` job, pinned `bandit==1.8.6`, MEDIUM+ threshold, identical command in CI, `scripts/verify.py` and `docs/security/pwa-hardening.md`, failure mode proven with a real MEDIUM fixture (`docs/audits/2026-09-21-pwa-08-sast.md`), frontend coverage measured and documented (Statements 55.65 % · Branches 48.64 % · Functions 49.34 % · Lines 58.22 %). The a11y finding #185 stays open as a PWA-10 item, not a PWA-08 one |
| PWA-09 | Operations: monitoring, sanitized versioned deployment topology and restore drill | **complete** — monitoring/readiness probe, sanitized topology and restore drill (#148, merged 2026-09-20T07:53Z) plus job-failure alarm semantics, unreadable-probe handling and the removable audit probe (#151, merged 2026-09-20T15:35Z); an external pager remains a documented operational boundary, not a closure gap |
| PWA-10 | Final desktop/mobile-PWA regression, accessibility/performance/install checks, closure decision and audit teardown | **all findings closed 2026-09-22; closure decision prepared, teardown still operator-gated** — a11y: the missing visible `h1` on `/login` (was inside a `hidden lg:block` panel) and the absent `h1` on `/forgot-password` and `/reset-password` are fixed and pinned by `public-page-headings.test.tsx` (#185, PR #189); offline: network-only navigation is now an accepted, tested decision (ADR 014, `sw-navigation-strategy.test.ts`) instead of an open question (#186). Performance (TTFB 17/14 ms, load 137/109 ms), install/artefacts (manifest + SW + icons 200, SW controls the page, static precache served offline), production+audit health smoke green. The production origin allowlist was verified end to end against the real proxy (#187): production origin → 401 (guard passes), foreign origin → 403 `ORIGIN_NOT_ALLOWED`; the check is now step 7 of `docs/ops/release-verification.md`. Go/No-Go packet: `pwa06-reacceptance/PWA-10-GO-NOGO-20260921.md`. Remaining operator gates: production deploy smoke and the audit teardown (needs explicit go) |

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
