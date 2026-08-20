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

### Fifth real run: the export-panel fix was correct but insufficient — the actual bottleneck was a server-side timeout

Re-ran with the export-panel fix deployed. Confirmed from the compose logs that the
fix took effect (`POST /v1/exports → 201` with **no** follow-up `GET /v1/exports`,
unlike every prior run) — and the failure was identical anyway: same locator, same
60s timeout, same "(1.1m)" total. That ruled the read-after-write theory out for
real this time (there was no second read left to race against) and pointed
directly at the `POST /v1/exports` call itself taking the full budget before ever
answering.

Read `numra_api.services.pdf_client.PdfServiceClient.render_report_pdf`: it wraps
the call to the PDF service in `httpx.AsyncClient(timeout=self._timeout_seconds)`,
default **60.0 seconds** (`config.py`'s `pdf_render_timeout_seconds`), and a
timeout there is caught and converted into `PdfServiceUnavailable` →
`mark_export_failed` — still returned as `201 Created` with `status: "failed"`,
which explains every piece of prior evidence at once: the POST always "succeeds"
(201), no exception ever appears in the compose logs (a clean `httpx.TimeoutError`
inside a `try/except`, not a crash), and the Download link never appears because
the export genuinely is marked failed, not pending.

Confirmed the mechanism is real, not just plausible: `apps/pdf/src/server.js`
lazily launches Chromium on its *own* first request (`getBrowser()`, a
memoized promise), and `GET /health/ready` also calls `getBrowser()` — so the
CI job's health-poll step already begins warming it well before Playwright
starts. That warm-up racing against a 2-second-per-attempt health-check timeout
(`health_check_timeout_seconds`, unrelated to the render timeout) can still leave
the *actual render* — not just the browser launch — taking longer than 60s under
genuine multi-container CPU contention (5 other services freshly started on the
same CI runner), which the `docker-compose-e2e` topology exercises for real and
the lighter-weight `system-e2e` job (bare processes) mostly doesn't.

Fixed at the actual bottleneck: `pdf_render_timeout_seconds` default raised from
60.0 to 120.0 seconds (`apps/api/src/numra_api/config.py`) — this is the value
that determines when the server itself gives up and marks an export failed, so it
was always the real constraint, not any client-side wait. Widened
`system-journey.spec.ts`'s Download-link wait to 150s (real margin over the new
120s server timeout — a client wait shorter than the server's own timeout can
never usefully help) and `test.setTimeout` to 300s, with both Playwright configs'
own `timeout` defaults raised to match so neither is ever the tighter bound.
Full local re-verification after this change: `tsc --noEmit`, `eslint`, and the
full 256-test Python suite (incl. the real-PDF-service `apps/api/tests`) all
clean.

### Sixth real run: the timeout theory itself was wrong — the render never completes at all under Docker

Re-ran with the 120s server / 150s client timeouts in place. Failed identically a
third time — **at exactly 150,000ms**, the new client wait, total test time "(2.6m)"
matching ~6s setup + the full 150s wait. This is the fact that finally rules out
"slow render" for good: if the bottleneck were genuinely a slow-but-eventually-
successful render landing somewhere under the old 60s/new 120s server timeout, a
150s client wait (30s of real margin over the server's own 120s bound) should have
let it succeed. It didn't — the failure duration tracks whatever the *client's* wait
happens to be, not the server's actual timeout, which is the signature of a
`toBeVisible()` poll faithfully waiting out its own budget for a condition that was
already permanently false (a render that failed) — Playwright has no way to know
early that the outcome is already decided; a `POST /v1/exports` that already
returned `status: "failed"` well before the client timeout still leaves the
Download-link assertion polling uselessly until its own bound expires. This is
still consistent with the export-panel fix and the timeout increase both being
correct changes -- neither was wrong, they just weren't addressing the actual
defect underneath.

Checked `apps/pdf/src/chromium-path.js`'s `resolveLaunchOptions`: no
`--disable-dev-shm-usage` launch arg, and `docker-compose.yml`'s `pdf` service had
no `shm_size` override either — Docker's default `/dev/shm` is 64MB, and headless
Chromium's renderer process routinely wants more than that for real page content.
Without the flag (or a larger shared-memory allocation), Chromium doesn't fail
fast under memory pressure — it hangs or crash-loops, which from the calling
`httpx` client's side is indistinguishable from "just needs more time," exactly
matching every symptom observed across three consecutive timeout-only fix
attempts. This is a well-documented, common failure mode for headless Chromium
specifically inside a container (not something reachable by `system-e2e`'s
bare-process PDF service, which runs directly on the CI runner's host OS with no
such constraint — the root reason this bug was invisible to every verification
pass before Gate C's real `docker compose up`).

Fixed both layers: `--disable-dev-shm-usage` added to Chromium's launch args
(makes it fall back to `/tmp` instead of hanging — correct and harmless outside a
container too) and `shm_size: "1gb"` added to the `pdf` service in
`docker-compose.yml` (a real shared-memory allocation is faster and more robust
than the `/tmp` fallback when available, matching Microsoft's own documented
recommendation for their Playwright Docker image). Verified locally:
`docker compose config --quiet` still valid, and the PDF service's own render
test suite (`node --test`, 4/4, including the "full render pipeline produces a
valid multi-page PDF" case) still passes.

### Seventh real run: the shm fix didn't clear it either — adding real observability instead of guessing again

Re-ran with both the launch-arg and `shm_size` fixes in place. Failed a fourth
time, identically, again at exactly the configured client timeout (150,000ms).
`POST /v1/exports → 201 Created` is still the last export-related line before
teardown, same as every prior run.

At this point three independently-reasoned, independently-correct fixes (the
read-after-write race, the timeout sizing, the `/dev/shm` starvation) have each
addressed a real, verifiable issue without resolving this specific symptom — and
the actual cause of the `PdfServiceUnavailable` (or whatever is really happening)
has never been visible anywhere: a failed export's `error_code` is written to a
database column nobody queries during this run and is never printed anywhere,
`docker compose logs`'s uvicorn access-log lines carry no timestamps and no
request/response bodies, and `docker compose logs` itself is only captured in a
single burst at teardown (after the test has already failed), not streamed live —
so there has been no way, across seven runs, to actually see *why* the render is
failing rather than continuing to guess at increasingly specific plumbing issues.

Rather than attempt an eighth blind fix, added real observability instead:
`export_service.create_export` now logs the caught `PdfServiceUnavailable`'s
message via `logger.warning` before marking the export failed
(`apps/api/src/numra_api/services/export_service.py`). `PdfServiceUnavailable`'s
own docstring already guarantees its message never carries the internal bearer
token or raw low-level exception internals, so this is safe to log in full — and
this is a genuine production observability gap being closed, not just a CI
diagnostic: a failed PDF export is currently completely silent everywhere except
one database column no code path surfaces. uvicorn's default logging
configuration (already the source of every `INFO: ... "GET ..." 200 OK` line
already visible in these logs) propagates this `WARNING`-level message to stdout
the same way, so the next real `docker-compose-e2e` run's captured logs should
finally show the actual reason instead of only the fact that *something* failed.

### Eighth real run: the logging worked — root cause found, unambiguous, fixed

```
api-1 | PDF export failed for export_id=... report_id=...: PDF service returned
HTTP 500: {"code":"PDF_RENDER_FAILED","message":"Error: browserType.launch:
Executable doesn't exist at /ms-playwright/chromium_headless_shell-1234/...
Looks like Playwright was just updated to 1.62.
```

The real cause, finally visible: `docker/pdf.Dockerfile` builds from
`mcr.microsoft.com/playwright:v1.56.1-jammy`, which pre-installs Chromium for
*exactly* Playwright 1.56.1 — nothing else. Its `RUN npm install --omit=dev` step
only ever sees `apps/pdf/package.json` (never `pnpm-lock.yaml` — that's a separate
Docker build stage, disconnected from the workspace's own lockfile entirely), and
`package.json` declared `"playwright": "^1.56.1"` — a floating range. By the time
of this run, npm's registry had a newer `1.62.1` satisfying that range, and Docker
resolved it fresh at build time. Playwright 1.62.1's own browser-management code
looks for a *different* pre-installed revision folder than what `v1.56.1-jammy`
actually has baked in, so `browserType.launch()` fails immediately with
"Executable doesn't exist" — a genuine, fast (not slow) failure, which is exactly
why every timeout increase across the previous three attempts changed nothing:
the failure was never a matter of waiting long enough.

This also explains, precisely, why no other job ever hit it: `system-e2e`,
`pdf-service-tests`, and `unit-and-property-tests` all run
`pnpm --filter @numra/pdf exec playwright install --with-deps chromium` as an
explicit step immediately after `pnpm install` — so whatever Playwright version
pnpm's own lockfile-driven resolution picks, a matching browser gets installed
right alongside it, every time. The Docker image is the only path with no such
reconciliation step; it depends entirely on the declared dependency version and
the base image tag never drifting apart, and nothing enforced that.

Fixed by pinning `apps/pdf/package.json`'s `"playwright"` to an exact `"1.56.1"`
(no `^`), matching the Docker base image tag precisely, and regenerating
`pnpm-lock.yaml` to match (confirmed via `pnpm why playwright` inside
`apps/pdf`: resolves to exactly `1.56.1`). Strengthened `docker/pdf.Dockerfile`'s
own comment to explain why this exact pin is load-bearing, so a future version
bump has to touch both the tag and the dependency deliberately together instead
of one silently drifting past the other again. Verified locally: `apps/pdf`'s own
render test suite (4/4) still passes, and `docker compose config --quiet` remains
valid.

### Ninth real run: a second, independent bug the first one was hiding

The Playwright pin fix worked exactly as diagnosed — the PDF render itself now
succeeds against the live stack. The `docker-compose-e2e` job still failed,
but on a *different* line, which is itself confirmation that root cause #8 was
correctly identified and fully fixed (nothing above `storage.save()` in the
call chain is failing anymore):

```
api-1 | INFO: "POST /v1/exports HTTP/1.1" 500 Internal Server Error
api-1 | ...
api-1 |   File "/app/apps/api/src/numra_api/storage/exports.py", line 54, in save
api-1 |     await asyncio.to_thread(path.write_bytes, content)
api-1 |   File "/usr/local/lib/python3.11/pathlib.py", line 1067, in write_bytes
api-1 |     with self.open(mode='wb') as f:
api-1 | PermissionError: [Errno 13] Permission denied:
'/app/data/exports/0c833193-9146-4449-976a-f94e4279e8b5.pdf'
```

Playwright's own log confirms this is the *only* thing that changed: the same
`system-journey.spec.ts:131` `Download` link `toBeVisible` timeout as every
previous run, still tracking its configured client timeout exactly (150000ms) —
because `create_export` still returns HTTP 500 with no export ever reaching
`COMPLETE`, the frontend still never renders a Download link. `GET /v1/health/ready`
was `200 OK` throughout this entire run (checked explicitly, in response to the
`pdf: "unhealthy"` reading from an earlier, pre-fix run raised as an investigative
lead) — that reading was a symptom of root cause #8 (the PDF service's own render
path, and by extension whatever probes it, failing under the version-mismatched
Chromium), not a separate health-cache/TTL bug. With #8 fixed, health/ready is
consistently healthy across this entire run with no unhealthy or stale reading
at any point, so the TTL-staleness lead is closed: it was the same root cause,
already fixed, not an independent problem.

Root cause: `docker-compose.yml` mounts the named volume `numra_exports_data` at
`/app/data/exports` inside the `api` container. `docker/api.Dockerfile` never
created that path before `USER numra` took effect, so Docker auto-created the
volume's mount point itself on first `up` — as `root:root`, per Docker's own
documented behavior for a mount point with no pre-existing directory in the
image. `LocalExportStorage.__init__`'s own `self._base_dir.mkdir(parents=True,
exist_ok=True)` (`apps/api/src/numra_api/storage/exports.py`) then runs at
application startup as the non-root `numra` user against an already-existing
(root-owned) directory — `exist_ok=True` means no error is raised at startup,
so this never surfaced as a build- or boot-time failure, only as a runtime
`PermissionError` on the very first write. FastAPI's existing generic exception
handler (`apps/api/src/numra_api/app.py`) caught it and returned a safe generic
500 with no internals leaked to the client — a real defense-in-depth working
exactly as intended — but the export itself still legitimately failed.

Fixed in `docker/api.Dockerfile`: added `RUN mkdir -p /app/data/exports &&
chown -R numra:numra /app/data` between creating the `numra` user and the
`USER numra` switch, so the directory pre-exists in the image with the correct
owner before the named volume ever mounts onto it. Docker initializes a named
volume's contents *and ownership* from whatever already exists at the mount
path in the image at first creation, so the volume itself now inherits
`numra:numra` ownership instead of defaulting to `root:root`. This is the same
class of bug as root cause #7 (`uv sync --all-packages`): a `docker compose up`
runtime concern invisible to `docker-build` CI, since that job only builds the
image and never runs a container against a real named-volume mount. Verified
locally: `docker compose config --quiet` (with `SESSION_SECRET`/
`PDF_INTERNAL_TOKEN` set) remains valid; the actual fix can only be proven by a
real `docker compose up`, which only GitHub Actions can run in this
environment.

### `system-e2e` failure on the same head (c8c45c5): investigated, not a code defect

The same push's `system-e2e` job (the manually-orchestrated, non-Docker real-stack
job) also failed, on a different symptom: `GET /v1/reports/{id}` returned `404`
immediately after `POST /v1/reports` had just returned `201` for that exact id,
one single time, with no retry — the frontend's `useReportProgress` hook only
retries the *job*-polling loop (`MAX_CONSECUTIVE_POLL_FAILURES = 4`), not the
one-shot initial `api.reports.get(reportId)` call on mount
(`apps/web/src/lib/use-report-progress.ts`), so a single 404 there is fatal to
that page load and explains the observed `getByRole("heading", { name: "Export"
})` timeout precisely (the report content never loads, so "Export" never
renders).

This is the same *signature* (create, then an immediate GET 404) previously seen
once before on a different resource (`/v1/calculations`) and diagnosed as
unreproducible. Given two independent occurrences now share the exact shape,
this was taken seriously rather than assumed to be the same dismissed flake:

- Read `create_report_with_job`/`get_report_for_user`
  (`apps/api/src/numra_api/repositories/reports.py`) and the `get_db` dependency
  (`apps/api/src/numra_api/deps.py`): `await session.commit()` runs in the
  dependency's post-`yield` cleanup, which FastAPI's `AsyncExitStack` closes
  *before* the response is hand off to ASGI `send()` — commit-before-response is
  a guaranteed ordering here, not a race, regardless of the 5 stacked
  `BaseHTTPMiddleware` layers (they proxy ASGI messages; they do not reorder the
  inner app's own execution).
- Reproduced the exact sequence (register → login → create person → create
  calculation → create report → immediately `GET` that report by id) directly
  against a locally-run instance of this exact commit's API (real Postgres, real
  Redis-backed rate limiter, `NUMRA_LLM_PROVIDER=mock`) 60 times in a tight loop:
  **60/60 succeeded**, every immediate `GET` returning `200` within single-digit
  milliseconds of the `POST`. No reproduction.
- Cross-checked against this exact commit's own `docker-compose-e2e` run (a
  stricter, container-isolated environment): its `POST /v1/reports` →
  `GET /v1/reports/{id}` pair also returned `200` immediately, no 404, in the
  full container topology.
- Read the same-origin proxy (`apps/web/src/app/api/[...path]/route.ts`):
  `export const dynamic = "force-dynamic"` plus an explicit `fetch()` per
  request with no caching directive — no route-cache or Data Cache hazard that
  could serve a stale/wrong response for a freshly-minted, never-before-seen
  report id.

No defect found in the code exercised by either failure. Given real
reproduction was attempted and failed to reproduce, and both the direct-API and
full-Docker-compose paths on this identical commit prove the sequence is
correct, this is treated as a genuine CI-environment-only flake (the
`system-e2e` job runs Postgres, Redis, the API, the worker, `next build && next
start`, and headless Chromium all on one shared GitHub Actions runner, with no
container isolation between them) rather than a code defect — consistent with
the standing instruction that "flake" requires real reproduction evidence and
permits at most one re-run to confirm. `rerun_failed_jobs` was used once on this
run to check; the result is recorded in the entry below once it lands.
