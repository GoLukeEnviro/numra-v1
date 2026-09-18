# PWA-04 automated two-account acceptance

Date: 2026-09-18

Environment: isolated `numra-rc2` Compose stack (`scripts/rc2-e2e.sh`), same
topology and flags as the `numra-audit` stack on HermesTrader.

Runner: `scripts/rc2-e2e.sh audit` (build + up + rate-limit reset + Playwright
+ down). Suite: `apps/web/e2e-system/rc2-two-account-journey.spec.ts`,
desktop 1440x900 + mobile 390x844.

## Why this replaces the manual login

The handoff recorded PWA-04 as blocked on a manual sign-in for the two
`@example.com` audit accounts. That block is avoidable: every non-production
stack runs with `ALLOW_SELF_SIGNUP=true`, and the journey registers its own two
accounts per run (`POST /api/v1/auth/register`, marked as an API-setup step; all
product assertions are real UI actions). No stored credential, no manual login,
and no real account is ever involved.

The same suite runs against the remote audit instance without code changes:

```bash
RC2_BASE_URL=https://hermestrader.taile6801f.ts.net:8444 \
RC2_MSG_PREFIX=AUDIT \
  npx playwright test --config=playwright.rc2.config.ts
```

`RC2_MSG_PREFIX` prefixes every free-text record with `AUDIT` so the PWA-01
cleanup inventory stays identifiable.

## Coverage added in this pass

Already present before this change: invitation/redeem, default consent display,
consent revoke + regrant (both directions, per-direction independence), dual
profile with master-number (22/4) shadow path, relationship type save/persist,
Dynamics (relationship analysis + shadow dynamics, COMPLETE on both viewports),
check-in round with joint analysis, shared task proposal + acceptance, roadmap
with review point + linked task, shared reflection copy, dissolution, read-only
history (check-ins/tasks/roadmaps/reflections), 409 `WORKSPACE_DISSOLVED`
mutation lock with same-origin guard.

Added here (the two remaining PWA-04 surfaces):

- **Relationship Copilot, both scopes.** Shared: A writes, B sees the same
  message in the same thread. Private: A's thread is invisible to B (asserted
  from B's own session), and the shared history is unaffected. The reply is the
  deterministic mock's fixed sentence (`Für diese Frage gibt es in den
  freigegebenen Daten noch keine ausreichende Grundlage.`), and the block also
  asserts the PR #98 regression directly: no `[system]` marker and no
  `profile_fact:` text may appear in the rendered DOM. Copilot history stays
  readable after dissolution with composing blocked.
- **Evidence layer.** A opens its SELF person's `/people/<id>/evidence` through
  the people list, saves a life-tracking day (mood 8 / energy 7 + note), and
  runs a pattern check; with a single observation the deterministic,
  versioned evidence policy honestly returns `NO_RELIABLE_PATTERN` — the
  qualified-result path stays covered by the mocked `e2e/evidence-layer.spec.ts`.
  Privacy: B opening the same evidence URL gets no title, no note, no metric
  badge — a non-owned person never leaks data.

## Flags

`docker-compose.rc2.yml` force-enables only five of the seven `AVENYTH_*` flags
before this change. Copilot and the evidence layer were therefore disabled on
this stack and could not be exercised non-mocked. Both flags are now enabled
here, matching what the handoff records for the real `numra-audit` stack
("all seven force-enabled"). Production defaults are untouched.

## Defects found and their disposition

1. **Register rate limit blocks repeat runs** — `POST /v1/auth/register` is
   capped at 5/hour per client IP; the journey registers two accounts per
   viewport (four per full run), and through the Next.js proxy the API always
   sees the web container's IP. A second run within the hour failed with
   `RATE_LIMIT_EXCEEDED` (retry after 3061s). Fixed in the runner, not the
   product: `scripts/rc2-e2e.sh reset-limits` clears the `auth:*` counters in
   the stack's Redis and runs automatically in `up` and `audit`. The limit
   itself is correct behaviour and stays.
2. **Dissolve read race in the journey** — the spec navigated to the workspace
   hub right after clicking dissolve; when the POST had not yet committed, the
   hub legitimately read `ACTIVE` and the assertion failed (seen once on
   desktop, green on re-run). The spec now `waitForResponse`s the dissolve POST
   before navigating. No product defect: the API returned
   `DISSOLVED` + `dissolved_at` for every post-commit GET.

No product defect required a code change in `apps/api` or `apps/web` in this
pass.

## Evidence

Per-viewport screenshots in `apps/web/test-results/rc2/<project>/`
(01-invitation-created … 14-evidence-no-reliable-pattern), produced by a real
browser against a real stack. Suite result and exit code are in the runner
output; CI parity: `.github/workflows/rc2-journey.yml` runs the same suite
(manual dispatch + weekly schedule).

## Known limits

- The audit instance run is read/write against the isolated `numra-audit`
  stack only; `numra-prod` is never touched.
- The Copilot reply text is the mock's fixed sentence by design; a real-provider
  acceptance run belongs to PWA-06.
- Evidence qualified-pattern rendering stays with the mocked spec; the
  deterministic policy needs 30 samples / 45 days and a 0.5 effect size, which
  a journey-sized run cannot reach honestly.
