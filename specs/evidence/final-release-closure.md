# Final Release Closure — evidence

Part of the "NUMRA V1 — FINAL RELEASE CLOSURE COMMAND" directive: close the
remaining release gates on top of the already-green PR #3
(`fix/numra-v1-production-completion`) — Next.js dependency security, an optional
live LLM smoke, a real `docker compose up` deployment, and final documentation
reconciliation. Every result below reflects a command actually executed and
observed in this session.

## Recon

```
$ git status --short
(clean)
$ git branch --show-current
fix/numra-v1-production-completion
$ git rev-parse HEAD
a7f42feafe56d2629a6fca9db5cf3a3a9c710e18
```

This is the same HEAD that had a real, fully-green (10/10) GitHub Actions run on
PR #3 immediately before this closure pass started (see `FINAL_VERIFICATION.md`'s
prior revision). Worktree was clean — no unrelated in-progress work to disturb.

## Live LLM credential check (Gate B, decided up front)

```
$ env | grep -iE "OLLAMA|NUMRA_LLM"
(no output)
```

No `OLLAMA_BASE_URL`, `OLLAMA_API_KEY`, `NUMRA_LLM_PROVIDER`, or model env vars are
set in this environment. Per the directive's own instruction ("do not invent them...
do not switch to mock and call it live"), this is recorded honestly as:

```
LIVE_LLM_SMOKE=NOT_VERIFIED
REASON=MISSING_CREDENTIALS
```

All other gates proceed regardless, as instructed.

## Baseline re-verification (before touching dependencies)

```
$ uv run pytest packages/engine-numerology/tests -q --cov=... --cov-fail-under=90
104 passed, TOTAL coverage 100.00%

$ uv run pytest packages apps/api/tests -q   (real Postgres + real PDF service)
256 passed

$ pnpm --filter @numra/web lint
(clean, 0 warnings)

$ pnpm --filter @numra/web exec tsc --noEmit
(clean)

$ pnpm --filter @numra/web test -- --run
39 passed (6 files)

$ pnpm --filter @numra/web build
all app routes compiled, incl. /icon.svg
```

Baseline is fully green — the earlier PR #3 HEAD (`a7f42fe`) is confirmed still
sound before starting the Next.js migration. No pre-existing failures to fix first.

(Note: the first attempt at the API test run showed 3 failures —
`test_delete_all_cascades_every_table`, `test_create_export_renders_real_pdf_and_downloads_it`,
`test_ready_with_mock_llm_and_real_pdf_service` — because this is a fresh sandbox
container and the real internal PDF service hadn't been started yet this session.
Started it (`PORT=4300 PDF_INTERNAL_TOKEN=... pnpm --filter @numra/pdf start`,
confirmed `{"status":"healthy","chromium":"healthy"}`) and re-ran: all 256 passed.
Not a real regression — environment setup, not a code bug.)

## Gate A — Next.js security remediation

### Before

```
$ pnpm audit --prod          25 vulnerabilities (2 low, 13 moderate, 10 high)
$ pnpm audit (incl. dev)     30 vulnerabilities (2 low, 16 moderate, 12 high)
```

All `next` advisories rooted in `next@14.2.35`. `npm view next dist-tags` showed the
`next-14` tag is pinned at exactly `14.2.35` — Next.js does not backport security
fixes onto the 14.x line at all; the maintained security-patch line is `backport`
(`15.5.23` at time of writing). The highest `patched_versions` floor across every
listed advisory was `>=15.5.21`, so a Next.js 15 migration was required (no patched
14.x exists) — done deliberately per the directive's own instruction, not a "prefer
14" shortcut that doesn't exist here.

`next@15.5.23`'s own peer dependencies (`react: ^18.2.0 || ...`) keep React 18.3.1 —
no forced React 19 migration. `eslint-config-next@15.5.23` still accepts ESLint 8.

### Migration safety audit (directive §6)

- `apps/web/src/app/api/[...path]/route.ts` — the one Route Handler using
  `context.params` directly. Next.js 15 made Route Handler `params` a `Promise`
  (previously a plain object) — fixed: `context: { params: Promise<{ path: string[] }> }`
  + `await context.params`. This is the proxy the whole app depends on for
  same-origin `/api/*`, multi-cookie forwarding, and Origin validation — verified
  working end-to-end by both the mocked Playwright journey and (later) the real
  system E2E journey against Docker Compose.
- All four dynamic page routes (`analysis/[calculationId]`, `people/[id]`,
  `relationships/[id]`, `reports/[reportId]`) use the client-side `useParams()` hook
  from `next/navigation`, not the server `params` prop — unaffected by the async-params
  change. Confirmed by reading each file before assuming safety.
- No `middleware.ts`, no `next/headers` (`cookies()`/`headers()`), no Server Actions,
  no `next/image` anywhere in the app — the three other largest Next 14→15 breaking
  surfaces (async `cookies()`/`headers()`, caching-default changes to Server Actions,
  `next/image` `sharp` requirement) are simply not present in this codebase to break.
- `next.config.mjs`'s `output: "standalone"` and hand-written CSP `headers()` needed
  no changes; both still work identically (confirmed by `docker-build` in Gate C).

### Nested/vendored transitive advisories

After the Next.js bump, `pnpm audit --prod` dropped from 25 to 5 (2 moderate, 3 high)
— all through `next@15.5.23`'s own **internal, hard-pinned** dependencies, not
anything in our own `package.json`: `next`'s `package.json` pins `"postcss": "8.4.31"`
exactly (no range) for its own CSS tooling, and declares `"sharp": "^0.34.3"` as an
`optionalDependencies` entry for `next/image` (which this app doesn't use at all —
confirmed via `grep -r "next/image" src`, no matches). Neither can be bumped by
changing our own `postcss` devDependency, since pnpm resolves next's internal copy
independently. Fixed with a root `pnpm.overrides` (`postcss: ^8.5.23`,
`sharp: ^0.35.0`) — the standard, minimal-intervention mechanism for forcing a
patched version of a dependency vendored inside another package's own tree.
Confirmed in the regenerated lockfile: `next@15.5.23`'s own `postcss` entry now
resolves to `8.5.26`, `sharp` to `0.35.3`.

`pnpm audit --prod` after the override: **0 vulnerabilities.**

The full audit (incl. devDependencies) then still showed 4 (3 moderate, 1 high) —
`esbuild`/`vite` dev-server-only advisories (path traversal / dev-server request
forgery, Windows NTLM hash disclosure — none reachable outside running `vite dev`
locally, never shipped to users) pulled in transitively by `vitest@3.2.6` pinning
`vite@5.4.21`. A patched `vite` (`>=6.4.3`) requires `vitest@^4.1.11`
(`vitest@latest`, stable, not a prerelease). Verified `@vitejs/plugin-react@4.7.0`
(already the resolved version) accepts `vite ^6.0.0` — no further bump needed there.
Added an explicit `vite: ^6.4.3` devDependency (vitest's own peer range on `vite` is
broad enough that pnpm was otherwise reusing the stale 5.4.21 lockfile entry rather
than resolving a fresh one) and bumped `vitest` to `^4.1.11`.

### After — full frontend regression re-run on Next.js 15.5.23 + vitest 4.1.11

```
$ pnpm --filter @numra/web lint                    clean, 0 warnings
$ pnpm --filter @numra/web exec tsc --noEmit        clean
$ pnpm --filter @numra/web test -- --run            39 passed (6 files), vitest v4.1.11
$ pnpm --filter @numra/web build                    all routes compiled, Next.js 15.5.23
$ pnpm --filter @numra/web exec playwright test     1 passed (golden journey, mocked)
$ pnpm --filter @numra/pdf test                     4 passed (unaffected, no dependency overlap)

$ pnpm audit --prod                                 No known vulnerabilities found
$ pnpm audit (incl. dev)                             No known vulnerabilities found
$ uvx pip-audit                                      No known vulnerabilities found
```

**Result: 25 → 0 vulnerabilities. No Critical, no High, no Moderate, no Low
remaining, in production or dev dependencies.**

One benign, pre-existing cosmetic warning observed (not introduced by this
migration, not a functional break): `next start` now explicitly warns that it
ignores `output: "standalone"` ("next start does not work with standalone
configuration"). Both Playwright configs (`playwright.config.ts`,
`playwright.system.config.ts`) use `next start` for local/CI test-server
convenience; this is intentionally NOT changed to hand-roll the standalone
server's static-asset copying in two more places, since Gate C's real
`docker compose up` is what actually validates the true standalone production
artifact end-to-end — that is the authoritative check for this exact concern, not
the test harness's dev-convenience server.

## Gate C — real docker compose deployment

### Local attempt: genuinely blocked, confirmed with authoritative evidence

`docker compose config --quiet` passes locally (valid compose file, all variables
resolve with the required env vars set).

`docker compose build` was attempted for real in this session (`dockerd` started
fresh via `setsid dockerd`, confirmed running via `docker info`). It fails
immediately at the very first image layer — pulling `ghcr.io/astral-sh/uv:0.5.11`
(and, in the prior session, `python:3.11-slim` from Docker Hub) — with `403
Forbidden` from the registry blob-storage host.

This session's sandbox routes all outbound HTTPS through a policy-enforcing agent
proxy (`/root/.ccr/README.md`). Its own diagnostic endpoint
(`curl $HTTPS_PROXY/__agentproxy/status`) records the authoritative reason, not
just the symptom:

```
{
  "kind": "connect_rejected",
  "detail": "gateway answered 403 to CONNECT (policy denial or upstream failure)",
  "host": "pkg-containers.githubusercontent.com:443"
}
{
  "kind": "connect_rejected",
  "detail": "gateway answered 403 to CONNECT (policy denial or upstream failure)",
  "host": "production.cloudfront.docker.com:443"
}
```

The proxy's own `noProxy` allowlist names specific language-package registries
(npm, PyPI, crates.io, Go proxy, JSR) that bypass it entirely — no container/OCI
registry host is on that list. The README's own explicit guidance for a 403 from
the proxy: "The destination host is not allowed by your organization's egress
policy for this session. Do not retry or route around it — report the blocked
host." This is the second time (across two separate sessions, now with the
proxy's own authoritative log rather than just inferring from the Docker CLI
error) that container-registry pulls are confirmed blocked at the sandbox's
network-policy layer — not a Docker daemon problem (the daemon starts and runs
fine), not a Dockerfile problem (the exact same Dockerfiles build successfully on
GitHub Actions runners, proven by the already-green `docker-build` CI job), and
not fixable by retrying, switching registries, or reconfiguring the daemon.

### Where Gate C is actually being proven: a real `docker-compose-e2e` CI job

The existing `docker-build` CI job only proves each image builds in isolation
(`docker build -f docker/api.Dockerfile --target api .` etc.) — it never runs
`docker compose up`, never exercises the real multi-service topology, and never
drives a browser through the composed stack. Since GitHub Actions runners
demonstrably have full container-registry access (the `docker-build` job pulls
`python:3.11-slim`, `ghcr.io/astral-sh/uv:0.5.11`, `node:20-slim`, and
`mcr.microsoft.com/playwright:v1.56.1-jammy` successfully every run) and this local
sandbox categorically does not, a new `docker-compose-e2e` job was added to
`.github/workflows/ci.yml` to do exactly what this gate demands, on the only
infrastructure actually capable of it:

1. `docker compose build` (the real Dockerfiles, the real compose topology).
2. `docker compose up -d` with `ENVIRONMENT=test`, `NUMRA_LLM_PROVIDER=mock`,
   `ALLOW_SELF_SIGNUP=true` — the one sanctioned exception for this exact gate
   (proving platform integration, not live LLM behavior; real credentials remain
   unavailable per Gate B).
3. Bounded-timeout polling of `GET /v1/health/live`, `GET /v1/health/ready` (real
   API container), and `GET /login` (real web container) — no component is assumed
   healthy without an actual successful response.
4. `docker compose ps --all` for the full service topology record. `migrate`'s exit
   code isn't separately parsed: `api`/`worker` both declare
   `depends_on: migrate: condition: service_completed_successfully`, so their
   answering the health polls above is itself proof `migrate` exited 0 — Compose
   would not have started them otherwise.
5. The real, non-`page.route()`-mocked system journey
   (`e2e-system/system-journey.spec.ts`) run through a new
   `playwright.compose.config.ts` that points at the already-running compose `web`
   container (port 3000) instead of starting its own Next.js server — same spec file
   as the existing `system-e2e` job, now exercised against the actual Docker Compose
   topology instead of manually-orchestrated bare processes.
6. A same-origin network assertion added directly to `system-journey.spec.ts`
   (`page.on("request", ...)` collecting every request whose port is `8000`/`8010`
   or whose hostname is `api`, asserted empty at the end of the journey) — proves
   the browser only ever calls same-origin `/api/*`, never the backend container
   directly, satisfying this gate's §15 requirement for both the compose run and the
   existing manually-orchestrated `system-e2e` run (the assertion is shared, so it
   now also strengthens that pre-existing job for free).
7. A log/secret audit (`docker compose logs --no-color`, scanned for
   `Traceback|Unhandled|FATAL|panic` and for the literal `SESSION_SECRET`/
   `PDF_INTERNAL_TOKEN` values leaking into any log line).
8. `docker compose down -v --remove-orphans` in an `if: always()` step, so the
   stack is torn down whether the run passed or failed.

This job's actual pass/fail result is recorded once GitHub Actions has run it for
real on the pushed HEAD (see the CI section below) — it is not fabricated here.
`DOCKER_COMPOSE_UP` in the final status block reflects that real run's outcome, not
an assumption.

### The real run immediately found a severe, previously-invisible bug

First `docker-compose-e2e` execution (head `1259ec3`) failed at `docker compose
up -d`, before any health poll or Playwright step ran:

```
Error response from daemon: failed to create task for container: failed to create
shim task: OCI runtime create failed: runc create failed: unable to start container
process: error during container init: exec: "alembic": executable file not found
in $PATH
```

Root cause, reproduced and confirmed locally (registries not needed for this —
pure `uv` dependency resolution against the already-vendored lockfile):
`docker/api.Dockerfile`'s `RUN uv sync --frozen --no-dev` (no `--all-packages`) at
the workspace root only syncs the *root* project — an empty placeholder
(`dependencies = []` in the top-level `pyproject.toml`) — not the workspace
members. This line was rewritten earlier in this same production-hardening
pass (see the `ec8291d` commit) to fix a different, real bug (`uv sync --package`
cannot be repeated), but the replacement's own reasoning — "a plain sync already
covers exactly [the workspace members]" — was itself wrong.

```
$ UV_PROJECT_ENVIRONMENT=/tmp/venv-test uv sync --frozen --no-dev   # the broken form
Audited in 0.02ms
$ /tmp/venv-test/bin/python -c "import numra_api"       ModuleNotFoundError
$ /tmp/venv-test/bin/python -c "import fastapi"         ModuleNotFoundError
$ /tmp/venv-test/bin/python -c "import alembic"         ModuleNotFoundError
$ ls /tmp/venv-test/bin | grep -E "alembic|uvicorn"     (nothing)

$ UV_PROJECT_ENVIRONMENT=/tmp/venv-test2 uv sync --frozen --no-dev --all-packages  # the fix
$ /tmp/venv-test2/bin/python -c "import numra_api; import fastapi; import alembic; \
    import numra_numerology; import numra_interpretation"   # all OK
$ ls /tmp/venv-test2/bin | grep -E "alembic|uvicorn"    alembic, uvicorn
```

**This means the `api` and `worker` production Docker images were completely
non-functional** — not just the `migrate` service. `uvicorn numra_api.app:app`
(api's `CMD`) and `python -m numra_api.worker` (worker's `CMD`) would have failed
identically to `migrate`'s `alembic` command, since none of `numra_api`, `fastapi`,
`uvicorn`, `sqlalchemy`, `alembic`, or any other workspace-member dependency was
actually present in the built image's venv. This was invisible to every
verification pass before this one because `docker-build` CI only *builds* each
image (`docker build -f docker/api.Dockerfile --target api .` etc.) — it never
*runs* one. This is the first time in the project's history anything has actually
executed a container built from this Dockerfile, and it found the images were
non-functional on the very first attempt.

Fixed with `uv sync --frozen --no-dev --all-packages` — confirmed by direct
reproduction (above) that this installs every workspace member's own dependencies,
not just the root placeholder's. Pushed as its own dedicated commit
(`9bb7f88`, severity-first ordering ahead of documentation work).

### Second real run: the image fix held, a real Origin-validation gap surfaced next

Head `9bb7f88`'s `docker-compose-e2e` run got much further: `docker compose build`
and `up -d` both succeeded, `migrate` completed, and the health-poll step's own
evidence is visible directly in the captured compose logs — `api-1` answered
`GET /v1/health/live` and `GET /v1/health/ready` with `200 OK` repeatedly, `web-1`
started ("✓ Ready"), confirming the critical image-build fix above is real and
holds under an actual `docker compose up`.

It then failed inside the real Playwright browser journey itself:

```
api-1  | INFO: ... "POST /v1/auth/register HTTP/1.1" 201 Created
api-1  | INFO: ... "GET /v1/auth/me HTTP/1.1" 401 Unauthorized
api-1  | INFO: ... "POST /v1/auth/login HTTP/1.1" 403 Forbidden
```

Root cause: `OriginValidationMiddleware` (`apps/api/src/numra_api/middleware/security.py`)
allows a request through when its `Origin` header is *absent* entirely, but rejects
one that's *present and not in `cors_allowed_origins`*. Registration in the spec
goes through `page.request.post()`, which sends no `Origin` header at all — so it
sailed through regardless of any mismatch. The real browser's login-form
submission sends a real `Origin`, and `playwright.compose.config.ts`'s `baseURL`
was `http://127.0.0.1:3000` — not in `cors_allowed_origins`'s default
(`http://localhost:3000`, `http://localhost:5173`; `config.py`). `docker-compose.yml`
has no env-var override for `cors_allowed_origins` at all, so there was nothing to
fix by configuring the CI job differently — the correct fix was the test config
itself: real users visit a compose deployment at its published `localhost` address,
not `127.0.0.1`, so `baseURL` now uses `http://localhost:3000` — which the API's
own existing default already allows, matching docker-compose.yml's real web port.
Fixed and pushed (`b8df216`).

### Third real run: through login, past export creation, stuck waiting on the Download link

Head `b8df216` got further still: registration and the real browser login both
succeeded (confirming the Origin fix), and the journey proceeded through profile
creation, the golden-value assertions, the Calculation Inspector, Dashboard, Today,
and real report generation. It then failed waiting up to 30s for the "Download"
link to appear after clicking "Export PDF" — even though the compose logs show
`POST /v1/exports` genuinely returned `201 Created` and the following
`GET /v1/exports` returned `200 OK`.

Read `export_service.create_export` (`apps/api/src/numra_api/services/`) end to end
to rule out a real backend bug before assuming a timing issue: it's genuinely
synchronous — it `await`s the PDF client's render, then calls `mark_export_complete`
(committing `status="complete"`), and only then returns; the route handler
serializes that same object directly as the `201` response body. `ExportOut.status`
and the frontend's `e.status === "complete"` filter (`export-panel.tsx`) use the
exact same string. Nothing here is capable of the failure mode of "succeeds but the
UI never notices."

The timing evidence points at genuine resource contention instead: the whole test
ran 36.55s in total (`Running 1 test` at `05:29:08.126` to the failure report at
`05:29:44.681`) before failing on a step with its own 30s timeout — meaning
everything before the export click (register, login, person creation, every
assertion, dashboard, today, and report generation, all with the near-instant mock
LLM) fit in roughly 6.5s, and the export step alone consumed the entire remaining
30s budget. That's consistent with a genuine, one-time Chromium cold start inside
the `pdf` container's very first render of the run, competing for CPU with five
other containers (postgres/redis/api/worker/web) all built and started moments
earlier on the same CI runner — a real condition the lighter-weight
manually-orchestrated `system-e2e` job (bare processes, no competing Docker
containers) doesn't encounter, which is exactly why Gate C's heavier, more
realistic topology is worth having as its own job rather than assuming the
existing one already covers it.

Fixed by widening the two most contention-sensitive waits in
`system-journey.spec.ts` — the shared spec file, so this also gives the
pre-existing `system-e2e` job more headroom for free: the Download-link wait from
30s to 60s (matching the precedent already set for report generation) and the
overall `test.setTimeout` from 120s to 180s so the two 60s allowances have room to
land back-to-back in a genuine worst case.

**This diagnosis turned out to be wrong** — recorded here rather than silently
rewritten, since the correction is itself part of the evidence. The fourth run
(below) hit the *identical* failure again, with the wait maxed out at exactly 60s
this time too — a resource-contention theory would predict the failure to clear
once at *some* generous-enough bound, not reproduce in lock-step with whatever the
timeout happens to be set to. That pattern means the awaited condition was never
going to become true no matter how long the test waited, which is the signature of
a real bug, not slowness.

### Fourth real run: same failure at 60s — a real bug, not slowness

Re-ran with the widened timeout. `docker compose logs` shows the full journey
succeeding well past the previous run's blocker — registration, login,
**`POST /v1/people/{id}/calculations` → 201** (proving the earlier `system-e2e`
404, see below, isn't a systemic regression), report generation, and
**`POST /v1/exports` → 201, `GET /v1/exports` → 200** — then the exact same
Download-link wait, maxed out at 60s again ("(1.1m)" total test time, matching
~6.5s of setup plus the full 60s budget exactly).

Re-read `export_service.create_export` once more, this time all the way through:
it calls `mark_export_complete`, which sets `export.status = ExportStatus.COMPLETE`
**on the in-memory object** and `await db.flush()`s it — then `create_export`
returns that same object directly, and the route serializes it as the `201`
response body. That response is therefore *already* the fully up-to-date record;
nothing a follow-up `GET /v1/exports` could return is more current. But
`export-panel.tsx`'s `handleExport()` discarded that response and re-fetched the
whole list instead (`await loadExports()`), then filtered for `status === "complete"`.
If anything about that separate GET's view of the world doesn't yet reflect the
write it's chasing — a real possibility once every hop between browser and
database goes through Docker's virtual network and its own connection/keep-alive
behavior, rather than bare loopback — the panel shows "No PDF has been rendered
for this report yet" and, critically, **never retries**: there is no polling loop,
so no amount of waiting fixes it once that single GET has already returned.

Fixed at the actual defect: `handleExport()` now merges the `created` export
(the POST response itself) directly into local state instead of re-fetching.
This removes the round-trip that could race, is strictly fewer network calls, and
is the correct fix regardless of whether the specific race is Docker-network
timing, connection pooling, or something else — the POST response was always the
authoritative answer.

### The system-e2e `POST /v1/people/{id}/calculations` 404 — investigated, not fixed as a code change

The other job (`system-e2e`) failed once on this same HEAD with
`POST /v1/people/{id}/calculations` → **404** immediately after a successful
`POST /v1/people` → 201, staying on `/people/new` instead of navigating to
`/analysis/{id}`. Read `get_person`/`create_calculation_route`/
`export_service`-adjacent code paths end to end and reproduced the identical
sequence twice, independently:

1. Directly against a freshly started API (curl, register → login → create
   person → create calculation): succeeded, correct golden values (`22/4`,
   `62/8`, `18/9`, `44/8`).
2. Through the real Next.js proxy this time (curl against a locally built `next
   start`, with a real `Origin` header): succeeded identically.

Both reproductions rule out the backend and the proxy as the cause. The
`docker-compose-e2e` run on this exact commit reached this same step and
succeeded (`POST /v1/people/{id}/calculations` → 201) — the same code, same
commit, different job. Combined with the two clean manual reproductions, this
is treated as a one-off flake, not a regression, per this directive's own
guidance not to chase single non-reproducing failures as root causes. Pushing the
real export-panel fix re-exercises this step naturally on the next CI run, which
doubles as the one permitted re-run to check whether it's genuinely reproducible.
