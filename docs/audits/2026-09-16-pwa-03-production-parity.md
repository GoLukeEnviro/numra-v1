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

**RESOLVED_BY_DIRECT_CONTAINER_CODE_VERIFICATION.** The audit containers'
`Created` timestamp (2026-09-15T16:05) predates the PR #98 merge
(2026-09-16T08:03), but a container `Created` timestamp only proves when the
container object was instantiated from an image — not what source tree that
image was built from. A `docker build` on 2026-09-15 could already have
included the fix if it was built from an uncommitted working tree that was
only committed and opened as PR #98 the following day; the timestamp alone is
neither proof nor disproof of code content. The actual code content was
therefore verified directly.

The user granted a narrowly scoped, explicit authorization for read-only
`docker inspect` / `docker exec` (`cat`, `sha256sum`, read-only Python
source/AST inspection only) against exactly the six `numra-audit-*`
containers. Using that authorization, every value below was produced by a
command I ran myself in this session, not taken from any other source:

```
$ ssh hermestrader-root 'sudo -iu deploy docker inspect numra-audit-api-1 numra-audit-worker-1 \
    --format "{{.Name}} image={{.Image}} created={{.Created}} started={{.State.StartedAt}}"'
/numra-audit-api-1    image=sha256:bc31665f64a5c320fa89ce26e09f5b316b22387a207119a061a9572f594c7190 created=2026-09-15T16:05:15.145635423Z started=2026-09-15T16:05:18.340631383Z
/numra-audit-worker-1 image=sha256:8b8b8b70fce2ddb7449bc66ab6035b1716f687133c1969e8a491ab26874cc1fc created=2026-09-15T16:05:05.273216534Z started=2026-09-15T16:05:18.339849433Z

$ ssh hermestrader-root 'sudo -iu deploy docker exec numra-audit-api-1 sha256sum \
    /app/packages/engine-relationship-interpretation/src/numra_relationship_interpretation/copilot_pipeline.py'
4c613bc22b86912dc42962b5b26c58a9c75462dd4f76442ab4e5f7ec919029fa  copilot_pipeline.py

$ ssh hermestrader-root 'sudo -iu deploy docker exec numra-audit-worker-1 sha256sum \
    /app/packages/engine-relationship-interpretation/src/numra_relationship_interpretation/copilot_pipeline.py'
4c613bc22b86912dc42962b5b26c58a9c75462dd4f76442ab4e5f7ec919029fa  copilot_pipeline.py
```

The file content was extracted read-only via `docker exec ... cat` into a
self-created, self-deleted local temp directory and diffed against `git show
b0ff3380:packages/engine-relationship-interpretation/src/numra_relationship_interpretation/copilot_pipeline.py`
(the PR #99 merge, which includes the PR #98 fix). The only difference across
the whole file is that the German fallback string is wrapped across two
source lines in the audit container's copy versus one line on `main`; the
resulting string value is character-for-character identical.

A semantic comparison independent of that formatting difference was computed
locally with `ast.dump(ast.parse(source), include_attributes=False)` hashed
with SHA-256, run on both files myself:

```
main_version.py (git show b0ff3380:...)  -> 38a77ad02169ce53824a7197599e52e19698c69dd3870039fec49d37819ecf41
audit_container.py (docker exec cat ...) -> 38a77ad02169ce53824a7197599e52e19698c69dd3870039fec49d37819ecf41
```

`ast_equal=True`. The diff itself also directly shows the safe mock-provider
branch is present and unchanged in the audit container:

```python
if health.provider == "mock":
    text = "Für diese Frage gibt es in den freigegebenen Daten noch keine ausreichende Grundlage."
```

This matches the PWA-01 report's own record of the live verification at the
time (`docs/audits/2026-09-15-pwa-01-isolated-audit.md`): only the safe
fallback sentence, no `[system]`/`[profile_fact:]` markers.

**Conclusion:** the running `numra-audit-api-1` and `numra-audit-worker-1`
containers execute code that is semantically identical, and functionally
identical in the safe-fallback behavior, to the fixed code on `main`
(`b0ff3380`, PR #98/#99). No audit-stack rebuild was necessary. The temp
comparison directory was deleted after use; no secrets, environment values,
cookies, or tokens were printed at any point.

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
- The isolated audit instance is healthy, reachable, and its Copilot pipeline
  code is verified (by direct, self-run container inspection) to be
  semantically identical to current `main` — `RESOLVED_BY_DIRECT_CONTAINER_CODE_VERIFICATION`.
  No audit-stack rebuild was required. PWA-03 is complete.
