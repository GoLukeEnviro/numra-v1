# PWA-01 isolated production audit

Date: 2026-09-15

Environment: isolated `numra-audit` stack on HermesTrader

Audit URL: `https://hermestrader.taile6801f.ts.net:8444/`

Production URL: `https://hermestrader.taile6801f.ts.net:8443/`

> **Host note (2026-09-19):** both stacks were migrated from the `HermesTrader`
> VPS to this host (`agent0-1`) with fresh secrets; the audit instance now runs as
> the `numra-audit` Compose project here. The URLs above are the historical
> HermesTrader origin and stay as written because this report documents that
> environment. The current audit origin is
> `https://agent0-1.taile6801f.ts.net:8444`; see `docs/ops/release-verification.md`
> and the environment table in "Synthetic cleanup inventory" below.

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

### Environments this inventory spans

Three environments hold synthetic audit records. They are separate data stores and
must be cleaned up separately — deleting in one never touches another:

| Environment | Where it runs | Data store | Audit endpoint |
|---|---|---|---|
| **HermesTrader audit** (historical) | VPS `HermesTrader` | that host's `numra-audit` Postgres volume | `https://hermestrader.taile6801f.ts.net:8444` (retired mapping) |
| **agent0 audit** (current) | this host, project `numra-audit` | container `numra-audit-postgres-1`, database `numra` | `https://agent0-1.taile6801f.ts.net:8444` |
| **RC2 local** (throwaway) | this host, project `numra-rc2` | container `numra-rc2-postgres-1` | local only |

`numra-prod` holds no audit records and is never part of any cleanup below.

### PWA-04 additions (RC2 automated two-account runs, 2026-09-18)

Added by the remote run recorded in `docs/audits/2026-09-18-pwa-04-automated-two-account.md`:

- HermesTrader audit environment:
  - Account `rc2-remote-probe-1789742261@example.com` — `6b807275-647d-4301-ab78-4fd03c2c79a7`
    (single registration probe)
  - Account `system-e2e-rc2-a-1789742293100-9ldy4i@example.com` (registered; journey did not finish)
  - Relationship workspace `bbf09486-badf-4b1a-b4cc-2cdc235e4ca8`

### agent0 audit additions (2026-09-19)

Added by the first full RC2 pass against the agent0 audit instance
(`RC2_MSG_PREFIX=AUDIT-AGENT0`), recorded in
`/home/hermes/reports/numra-agent0-migration-report-20260919.md` until that report
is folded into the repository:

- Accounts (agent0 audit environment):
  - `system-e2e-rc2-a-1789828234271-2mxgwu@example.com` — `2e44d465-5a98-45dd-a1fa-2c0159635086`
  - `system-e2e-rc2-b-1789828234271-18iv52@example.com` — `91266cfc-9764-4960-a201-39e1af663b67`
  - `system-e2e-rc2-a-1789828275131-6p7fyo@example.com` — `98ff5c79-80dc-4213-bc40-c1754b9ca247`
  - `system-e2e-rc2-b-1789828275131-mvg224@example.com` — `00db0e69-f225-457f-af22-ee97388ec78b`
- Relationship workspaces (both `DISSOLVED`):
  - `e1a1f083-b040-419a-82cf-38fba7904b6b`
  - `f63adcf3-043f-44b3-8dfa-4783b0b542bb`
- Person profiles (SELF, both members of each workspace):
  - `26ef2f22-fcc5-4e40-a737-8d7ab4070360`, `9afff1b1-2b30-45ad-8931-62bb963aea44`
  - `6409f2e6-e1eb-4ee6-9ec5-788af1eab409`, `c7b4d76a-424b-4e33-894c-56942830ab33`
- Aggregate counters in that database (read-only, 2026-09-19): users 4,
  relationship_workspaces 2, people 4, analysis_jobs 3 (all COMPLETE),
  relationship_analyses 1, shadow_dynamics_analyses 2, reports 0, chat_threads 4.

### RC2 local (throwaway, no inventory entry needed)

The `numra-rc2` Compose project is created and destroyed by `scripts/rc2-e2e.sh`
itself: `audit` and `down` both run `docker compose down -v`, which removes the
project's Postgres and export volumes. Records created by a local run never
outlive the run. **Cleanup owner: the runner**; no manual step is required, and
no `numra-rc2` containers or volumes exist between runs.

### Cleanup ownership and deletion condition (all environments)

- **Owner:** the PWA-10 closure gate. Nothing above is deleted before a
  documented Go in PWA-10 — the records are the reproducibility evidence for
  PWA-01/PWA-04.
- **Condition:** the documented PWA-10 Go, per `docs/planning/avenyth-pwa-execution-state.md`
  ("PWA-10 is the only gate that authorizes deletion of audit records and
  retirement of the isolated audit stack").
- **Production:** `numra-prod` appears in this inventory only to state that it
  holds no audit records; it is never cleaned up.

### Stored prompt-scaffolding rows (counted, not yet cleaned)

The mock-provider prompt echo (defect recorded above) was persisted into
`result_json` before PR #112 closed the leak class for every pipeline. Read-only
count as of 2026-09-19 in the **agent0 audit** database:

| Table | Rows with scaffolding markers |
|---|---|
| `relationship_analyses` | 1 of 1 |
| `shadow_dynamics_analyses` | 2 of 2 |

Markers checked: `[system]`, `profile_fact:`. No row content was read or
recorded. These rows live only in the isolated audit database; production is
unaffected (`NUMRA_LLM_PROVIDER=disabled` there). They are counted here so the
PWA-10 cleanup covers them; the deletion itself follows the same Go gate as the
rest of this inventory.

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
