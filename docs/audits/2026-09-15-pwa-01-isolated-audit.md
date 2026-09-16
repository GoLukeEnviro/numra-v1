# PWA-01 isolated production audit

Date: 2026-09-15

Environment: isolated `numra-audit` stack on HermesTrader

Audit URL: `https://hermestrader.taile6801f.ts.net:8444/`

Production URL: `https://hermestrader.taile6801f.ts.net:8443/`

## Safety boundary

- The audit stack uses its own Compose project, network, PostgreSQL volume, export volume, API port, and web port.
- Production stayed online and healthy throughout the audit.
- Only synthetic data was used. No personal account, production user data, password, cookie, session token, CSRF token, or authorization header is recorded here.
- The audit LLM provider is the deterministic mock provider, so the run incurs no external LLM cost.

## Synthetic cleanup inventory

Run tag: `1789487271746`

- Accounts:
  - `audit-a-1789487271746@example.com`
  - `audit-b-1789487271746@example.com`
- Person profiles:
  - `bfcbcafc-0a8e-4c73-bc3a-e14c922837c7` — AUDIT Alexandra-Synthetica (display name AUDIT Alex)
  - `b57c2306-8574-44fb-9448-dd7e68986975` — AUDIT Maximilian-Außergewöhnlich (display name AUDIT Max)
- Relationship workspace:
  - `f3ce1d00-7334-41c7-a204-c219abe0e6e3`
- Personal content owned by Audit A:
  - 10 tasks
  - 3 notes
  - 4 long reflections
- Shared workspace content:
  - 3 tasks, including one proposal accepted by Audit B
  - 2 accepted roadmaps
  - 6 milestones
  - 1 shared reflection copied from Audit A
  - 1 completed check-in round with answers from both accounts
  - 1 archived Copilot thread containing the original mock-provider defect reproduction
  - 1 active Copilot thread containing the post-fix verification message and safe response

All disposable titles and free-text records use the `AUDIT` prefix where the product surface permits it. The run tag, account addresses, person IDs, and workspace ID are sufficient to identify the remaining records for cleanup.

## Verified product flows

- Self-sign-up and separate authenticated sessions for Audit A and Audit B
- Person profile creation with long synthetic names
- Connection invitation, acceptance, and relationship workspace creation
- Mutual consent display and shared workspace activation
- Dense personal tasks, notes, and reflections
- Shared task creation and proposal acceptance
- Roadmap creation, milestone rendering, and acceptance by the second account
- Reflection sharing
- Check-in submission by both accounts and joint analysis rendering
- Shared relationship Copilot message flow
- Dashboard, Today, Connections, Workspaces, People, workspace overview, Dynamics, Check-ins, Tasks, Roadmaps, Shared Reflections, Copilot, Consent, Reports, Settings, Privacy, and new-person routes render without browser console errors

## Defect found and fixed

The generic mock LLM provider echoed its complete request into the user-facing relationship Copilot response. That exposed internal prompt text and grounded context inside the synthetic shared thread.

The relationship Copilot pipeline now replaces mock-provider output with the existing safe insufficient-evidence sentence. The generic mock remains unchanged for non-user-facing test/report behavior, and real providers are unaffected.

Verification:

- A regression test first reproduced the prompt echo.
- The focused Copilot pipeline suite passes: 6 tests.
- The relationship interpretation unit suite passes: 52 tests.
- Ruff passes for both changed files.
- The patched audit API and worker images were rebuilt.
- Live shared-thread verification returned only: `Für diese Frage gibt es in den freigegebenen Daten noch keine ausreichende Grundlage.`
- The live DOM contained neither `[system]` nor `[profile_fact:` markers.
- Audit and production health checks remained green after deployment.

## Known audit limits

- The synthetic `example.com` accounts are intentionally not email-verified, so the verification reminder remains visible.
- Dynamics currently renders its empty state because no separate relationship-analysis generation was performed.
- Reports and the personal Copilot render their empty states; no paid/external report generation or real LLM call was made.
- The direct `/reflections` path is not a product navigation route and returns 404; shared reflections are available inside the relationship workspace.
- Synthetic data has not been deleted yet so the evidence state remains reproducible.

## Cleanup sequence after closure

1. Preserve any final evidence that is still required.
2. Delete the two synthetic accounts, using the run-tagged email addresses above.
3. Confirm the relationship workspace and all dependent shared records are removed.
4. Remove the isolated `numra-audit` Compose stack and its two audit-only data volumes if the environment is no longer needed.
5. Remove the audit-only Tailscale Serve mapping after the stack is retired.
