# AVENYTH PWA Product Closure — Session Handoff (2026-09-18)

Purpose: let any agent (Claude, Codex, or a human) pick up PWA Product
Closure work at PWA-04 without re-deriving context. This is a handoff
report, not a new plan — the canonical roadmap remains
`docs/planning/avenyth-pwa-execution-state.md`.

## Repository / CI state at handoff

- `origin/main` HEAD: `b39ea41e79f2be92e3a040acbe2cc91f1cd65686`
  (merge of PR #102, post-merge CI green, 12/12 required checks).
- Production deployed SHA at last check: `b0ff3380be1765a1b438283cfdad4656c9890d73`
  (PR #99). The ~11-minute auto-deploy timer on HermesTrader may have since
  picked up later commits — re-verify before relying on this, do not assume.
- Local checkout at `E:\VS-code-Projekte-5.2025\numra-v1` is on `main`,
  clean, fully synced with `origin/main`.
- Four stale worktrees (`numra-v1-ollama-top-p`, `numra-v1-pr-web-03`,
  `numra-v1-pr-web-04`, `numra-v1-pr-web-06a`) were removed from Git's
  worktree tracking during this handoff — all four branches were already
  merged (PR #41, #42, #73, #74) with zero uncommitted local changes. Their
  on-disk directories may still physically exist (Windows `git worktree
  remove` reported "Filename too long" but the tracking was cleaned) —
  safe to delete manually if still present, no repo content is at risk.

## What is done (PWA-01 through PWA-03) — do not redo this

| Phase | State | Evidence |
|---|---|---|
| PWA-01 | complete | `docs/audits/2026-09-15-pwa-01-isolated-audit.md` |
| PWA-02 | complete | PR #99, #100 merged; `docs/planning/avenyth-pwa-execution-state.md` is canonical |
| PWA-03 | complete | `docs/audits/2026-09-16-pwa-03-production-parity.md` — production flags/topology verified read-only; audit-instance code parity with `main` verified directly via self-run `docker inspect`/`docker exec` (raw SHA-256, line diff, semantic Python AST hash) — `RESOLVED_BY_DIRECT_CONTAINER_CODE_VERIFICATION`, no audit-stack rebuild was needed |

All seven `AVENYTH_*` V2 feature flags remain **disabled in real
production** — this is an intentional, standing product decision, not a
defect. The isolated `numra-audit` Compose stack has them force-enabled and
is where all of PWA-04 onward happens.

## PWA-04 — status: BLOCKED, not started

**What was attempted:** navigated a browser tab to the audit instance
(`https://hermestrader.taile6801f.ts.net:8444/login`) to resume the two
synthetic accounts from PWA-01 (`audit-a-1789487271746@example.com`,
`audit-b-1789487271746@example.com`). Both sessions had expired (redirected
to `/login`).

**Safety incident (caught, no harm done):** the browser's autofill
pre-populated the login form with the user's real personal email address
instead of the synthetic audit address. This was caught and flagged before
any submission — the form was never submitted with the real address, no
real account was touched. **Whoever resumes this: always visually confirm
the email field reads an `@example.com` / `AUDIT-`-prefixed synthetic
address before submitting the login form on the audit instance.**

**Why it's still blocked:** the user began correcting the email field and
had not yet entered the password or clicked "Anmelden" when the session's
browser-automation tool connection (`mcp__claude-in-chrome__*`) was dropped
by the harness ("MCP server disconnected"). No further browser action was
possible after that point in this session.

**Exact next step:** in a session with working browser tools (or the user
acting manually), open `https://hermestrader.taile6801f.ts.net:8444/login`,
sign in as `audit-a-1789487271746@example.com` (credentials are wherever
they were recorded when the account was created in PWA-01 — Claude has
never had and must never be given the password; use "Passwort vergessen?"
to reset it if it cannot be found), then repeat for
`audit-b-1789487271746@example.com` in a second browser tab/context so both
accounts have simultaneous authenticated sessions.

## PWA-04 scope once both accounts are authenticated

Per `docs/planning/avenyth-pwa-execution-state.md` and
`docs/plans/2026-09-16-pwa-product-closure.md`:

1. Generate the relationship analysis for the existing workspace
   (`f3ce1d00-7334-41c7-a204-c219abe0e6e3` per the PWA-01 inventory —
   re-verify it still exists before reusing it) — Dynamics was left empty
   in PWA-01 because this step wasn't run yet.
2. Verify private vs. shared visibility boundaries for both accounts.
3. Verify consent: revoke, and re-grant: confirm the workspace/shared
   surfaces correctly gate on current consent state, not just initial grant.
4. Exercise check-ins, tasks, roadmaps, reflections, Copilot, evidence with
   both accounts, building on the dense synthetic state from PWA-01.
5. Exercise dissolution: dissolve the relationship, then verify read-only
   history and blocked mutations afterward.
6. Screenshots/evidence must only ever contain synthetic (`AUDIT`-prefixed
   where the product surface allows it) data — never real names or content.
7. Fix any defect found test-driven (reproducing test first), same PR/CI/
   merge discipline as PWA-01 through PWA-03 (small focused PR, wait for
   all 12 required checks, self-verify diff, merge, check post-merge CI).
8. Document findings in a new `docs/audits/2026-09-1X-pwa-04-*.md` file and
   update `docs/planning/avenyth-pwa-execution-state.md`
   (`CURRENT_TASK`/`NEXT_ACTION`/roadmap table) the same way PWA-01–03 did.

## Remaining roadmap after PWA-04 (unchanged, still queued)

- **PWA-05** — controlled email lifecycle (verify, resend, forgot/reset,
  anti-enumeration) using only audit-controlled inboxes. If no controlled
  inbox is available, this is a legitimate stop condition — ask for exactly
  the one needed manual action, never ask for or store credentials/tokens.
- **PWA-06** — Personal Copilot, real-provider report generation, PDF
  download, all with synthetic data; no internal prompts/secrets may appear
  in any produced artifact.
- **PWA-07** — export, account deletion, and cascade-cleanup proof using a
  separate, expendable synthetic account (do **not** delete the PWA-01/
  PWA-04 accounts yet — they're needed until PWA-10's Go-gate).
- **PWA-08** — triage the one open moderate Dependabot security alert,
  address Node-20 GitHub Actions deprecation warnings if still present, CSP
  hardening (remove `unsafe-inline` where compatible), add a pinned SAST
  check, close targeted frontend coverage gaps.
- **PWA-09** — version a secret-free production topology/template, add
  health/job/error monitoring with alerts, run one backup restore drill into
  an isolated target (never overwrite production), document the drill.
- **PWA-10** — final full regression: all 12 required checks, desktop +
  mobile-responsive journeys, accessibility, performance budgets, PWA
  install/offline/update behavior, production re-verification. Write
  `docs/releases/pwa-product-closure.md` with scope, evidence links, known
  risks, and an explicit Go/No-Go decision. **Only on a documented Go**:
  clean up the exact synthetic accounts/records inventoried in
  `docs/audits/2026-09-15-pwa-01-isolated-audit.md` (and whatever PWA-04–07
  add to that inventory), confirm cascades, remove the `numra-audit`
  Compose stack + its two audit-only volumes + its Tailscale Serve mapping
  (port 8444), and re-verify `numra-prod` health afterward.

## Standing constraints (apply to every remaining phase)

- Never request, read, store, or print passwords, tokens, cookies, session
  values, or full environment files — for any account, synthetic or real.
- Only ever use the two (or more, if created) dedicated synthetic
  `@example.com` audit accounts; never a real personal account.
- All merges follow: dedicated branch → small focused PR → wait for all 12
  required GitHub Actions checks (discover the actual list via `gh api
  repos/GoLukeEnviro/numra-v1/branches/main/protection --jq
  '.required_status_checks.contexts'`, never hardcode a count) → independent
  diff review → merge → verify post-merge CI on `main`.
- HermesTrader access: always `ssh hermestrader-root` as transport only,
  then the documented `deploy` identity for repo/compose work — read
  `C:\Users\CodeLuke\.codex\HERMESTRADER-WRITER-MEMORY.md` and
  `C:\Users\CodeLuke\.claude\HermesTrader-Zugang-Quickref.md` in full before
  any HermesTrader action. Never `git reset --hard`, `clean`, `prune`,
  force-push, or direct commits to `main`.
- `numra-prod` is never modified by this roadmap; all interactive testing
  happens against the isolated `numra-audit` Compose stack
  (`/opt/numra-audit/compose.audit.yml`, `/etc/numra-audit.env`, ports
  17301/17801, Tailscale Serve `:8444`).
- Claim success only after fresh, self-run verification — never repeat an
  unverified claim (this session specifically caught and rejected two
  fabricated-looking "verification" claims about audit/production code
  parity from unclear sources before independently re-deriving the same
  conclusion itself — see the full conversation transcript around
  2026-09-16 for that incident if precedent is useful).

## Reference documents

- `docs/planning/avenyth-pwa-execution-state.md` — canonical execution
  state, update after every phase.
- `docs/plans/2026-09-16-pwa-product-closure.md` — full phase-by-phase plan.
- `docs/audits/2026-09-15-pwa-01-isolated-audit.md` — synthetic account/data
  inventory, must stay accurate as PWA-04+ adds more records.
- `docs/audits/2026-09-16-pwa-03-production-parity.md` — production and
  audit-instance verification method and results.
- `C:\Users\CodeLuke\.claude\plans\quiet-noodling-gosling.md` — original
  approved PWA plan (superseded in detail by the two docs above, kept as
  historical rationale for the web/PWA-over-native-mobile decision).
