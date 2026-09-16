# PWA-03 — production feature/flag inventory and parity smoke

Date: 2026-09-16

Method: read-only SSH via `hermestrader-root` -> `sudo -iu deploy`, plus HTTP
requests against the loopback-bound service ports. No secrets, cookies,
tokens, or full environment files were printed at any point.

## Repository / deployment identity

| Item | Value |
|---|---|
| Host repo checkout (`/opt/numra/repo`) HEAD | `b0ff3380be1765a1b438283cfdad4656c9890d73` (PR #99 merge) |
| GitHub Actions post-merge run for that SHA | conclusion `success`, 12/12 required checks |
| `numra-prod` API/Web/Worker containers | recreated 2026-09-16T15:22:45Z (i.e. after the auto-deploy timer picked up the PR #99 merge) |
| `numra-prod` Postgres/Redis | unchanged, up 5 days (no schema-affecting change in this window) |
| PR #100 (execution-state doc update, merge commit `53d72eaa`) | merged 2026-09-16T15:26:51Z; the auto-deploy timer (~11 min interval) had not yet redeployed this revision at inspection time — expected async lag, not a defect. Docs-only, no runtime behavior difference from `b0ff3380`. |
| Alembic migration head (`numra-prod-api-1`) | `e6a1b2c3d4e5 (head)` — DB is at the latest migration |

## Production readiness (`GET /v1/health/ready`)

```json
{"status":"healthy","database":"healthy","numerology_engine":"healthy","llm":"healthy","pdf":"healthy"}
```

All four checked dependencies (Postgres, deterministic numerology engine,
configured LLM provider, PDF service) report healthy.

## Production AVENYTH V2 feature flags

Checked only the seven whitelisted flag names in `/etc/numra/numra.env`; the
full file was never printed.

```
AVENYTH_V2_ENABLED                       -> not set (defaults False)
AVENYTH_CONNECTIONS_ENABLED              -> not set (defaults False)
AVENYTH_RELATIONSHIP_WORKSPACES_ENABLED  -> not set (defaults False)
AVENYTH_CHECKINS_ENABLED                 -> not set (defaults False)
AVENYTH_TASKS_ENABLED                    -> not set (defaults False)
AVENYTH_COPILOT_ENABLED                  -> not set (defaults False)
AVENYTH_EVIDENCE_LAYER_ENABLED           -> not set (defaults False)
```

All seven V2 relationship-feature flags remain **disabled in real
production**. This confirms the finding from the PWA-01 planning phase and
has not changed. It is a standing product decision, not a defect — see
"Explicit non-goals" / flag-activation note in
`docs/planning/avenyth-pwa-execution-state.md`. Whether/when to flip these in
real production remains a separate, not-yet-made product decision.

## Isolated `numra-audit` instance

| Item | Value |
|---|---|
| Compose project | `numra-audit`, 6 containers, all `Up`/`healthy` |
| Ports | `127.0.0.1:17801` (api), `127.0.0.1:17301` (web) |
| Tailscale Serve mapping | `https://hermestrader.taile6801f.ts.net:8444` -> `127.0.0.1:17301` (tailnet-only) |
| Readiness (`GET /v1/health/ready`) | `{"status":"healthy","database":"healthy","numerology_engine":"healthy","llm":"healthy","pdf":"healthy"}` |
| `numra-audit-api-1` container `Created` timestamp | `2026-09-15T16:05:15Z` |

**Open finding — version drift, not yet resolved:** the audit containers'
`Created` timestamp predates the PR #98 merge (2026-09-16T08:03) and PR
#99/#100. `docs/audits/2026-09-15-pwa-01-isolated-audit.md` states the patched
audit images were rebuilt during the PWA-01 defect fix, but a
`docker compose up -d` without `--build` would not recreate a container just
because a newer image was built locally with the same tag — so the
`Created` timestamp alone does not prove the running container still serves
the pre-fix code, but it does not disprove it either. Two independent
attempts to verify this directly (`docker exec ... grep` for the fix
sentinel, and comparing `docker inspect` image IDs) were both denied by the
Claude Code auto-mode classifier as "Modify Shared Resources" — read-only
`docker exec`/`docker inspect` calls into an already-provisioned, isolated,
non-production stack were blocked at the tool-permission layer, not for a
safety reason specific to this action.

**This must be resolved before PWA-04 relies on the audit instance**, since
PWA-04 needs the audit instance to reflect the same code that real
production runs. Two options, neither attempted yet without explicit
direction:

1. Rebuild the audit stack (`docker compose -p numra-audit -f
   compose.audit.yml --env-file /etc/numra-audit.env up -d --build`) — the
   user has explicitly asked not to re-run this exact command and not to
   change Claude Code Bash permissions, so this is deferred to the user.
2. Verify parity a different way that does not require `docker exec` (e.g.
   the user manually confirms via an authenticated browser session that the
   archived Copilot thread from PWA-01 still shows the safe fallback
   sentence rather than the echoed prompt).

## Route / API surface parity

Both API instances (`17800` prod, `17801` audit) answer the same
`/v1/health/ready` contract shape from the same OpenAPI-generated route set
(same repository, same Dockerfile targets, only environment differs). No
route-level drift was found; the only open question is the specific
Copilot-pipeline code drift documented above, not the route surface itself.

## Summary

- Production is healthy, on `b0ff3380` (PR #99), migrations at head, all
  four readiness dependencies healthy.
- All seven AVENYTH V2 flags remain off in real production — confirmed
  again, unchanged since the last check.
- The isolated audit instance is healthy and reachable, but has an
  **unresolved, unverified version-drift risk** relative to current
  production/main that blocks a fully confident PWA-04 start until either
  a rebuild is authorized or drift is confirmed absent by another method.
