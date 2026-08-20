# Real system E2E — evidence

Part of the "FINAL COMPLETION, PRODUCTION HARDENING" directive, P1 VERIFICATION item 16
("a real, non-`page.route()`-mocked system E2E Playwright test exercising the full
stack including a real PDF export and Delete-All").

## What this proves that `golden-journey.spec.ts` cannot

`apps/web/e2e/golden-journey.spec.ts` intercepts every API call with `page.route()`
and answers with hand-shaped fixture data — it never reaches a real backend, so it
cannot catch a bug that only exists in the gap between what the live engine/API
actually returns and what the frontend was built/tested against.

`apps/web/e2e-system/system-journey.spec.ts` (config:
`apps/web/playwright.system.config.ts`) makes zero `page.route()` calls. Every request
the browser makes goes through the real same-origin proxy
(`apps/web/src/app/api/[...path]/route.ts`) to a real, running FastAPI instance.

**This is exactly what it was built to catch, and did**: the first run against the
live stack reproducibly crashed on the Calculation Inspector tab
(`TypeError: Cannot read properties of undefined (reading 'length')`) — a genuine
frontend/backend contract drift (`diagnostics.life_path.alternative_methods
.direct_digit_sum` was being serialized as a full `CalculationMetric`, which has no
`reduction_steps` field, instead of the flat shape the pinned golden fixture and the
frontend's `DiagnosticAlternative` type actually document) that the mocked suite,
which only ever exercises the fixture's own already-correct shape, could never have
surfaced. Fixed in `date_metrics.diagnostic_payload` (see the corresponding commit).
Confirmed reproducible 100% (5/5 runs) before the fix, three consecutive clean runs
after it.

## Prerequisites (all real, none mocked)

The spec itself starts only the Next.js server (its `webServer` config). Everything
else must already be running, pointed at one dedicated database:

```bash
# 1. Postgres + Redis (already running in most dev setups; shown for a from-scratch host)
pg_ctlcluster 16 main start
redis-server --daemonize yes --port 6379

# 2. A dedicated e2e database, migrated
createdb -O numra numra_e2e
DATABASE_URL=postgresql+asyncpg://numra:numra_dev_password@127.0.0.1:5432/numra_e2e \
  uv run --directory apps/api alembic upgrade head

# 3. The real internal PDF service (Playwright/Chromium)
cd apps/pdf && PORT=4300 PDF_INTERNAL_TOKEN=test-token node src/server.js &

# 4. A real FastAPI instance — NUMRA_LLM_PROVIDER=mock is an explicit, non-implicit
#    choice (see numra_api.services.llm_factory); ALLOW_SELF_SIGNUP=true only because
#    there is no registration UI to drive from the browser, so the spec registers its
#    throwaway account directly against the API instead.
cd apps/api && \
  DATABASE_URL=postgresql+asyncpg://numra:numra_dev_password@127.0.0.1:5432/numra_e2e \
  ENVIRONMENT=test ALLOW_SELF_SIGNUP=true NUMRA_LLM_PROVIDER=mock \
  PDF_INTERNAL_URL=http://127.0.0.1:4300 PDF_INTERNAL_TOKEN=test-token \
  EXPORT_STORAGE_DIR=/tmp/numra-e2e-exports \
  RATE_LIMIT_BACKEND=redis REDIS_URL=redis://127.0.0.1:6379/2 \
  CORS_ALLOWED_ORIGINS='["http://127.0.0.1:4180"]' \
  uv run uvicorn numra_api.app:app --host 127.0.0.1 --port 8010 &

# 5. A real report worker against the same database
cd apps/api && \
  DATABASE_URL=postgresql+asyncpg://numra:numra_dev_password@127.0.0.1:5432/numra_e2e \
  ENVIRONMENT=test NUMRA_LLM_PROVIDER=mock \
  PDF_INTERNAL_URL=http://127.0.0.1:4300 PDF_INTERNAL_TOKEN=test-token \
  EXPORT_STORAGE_DIR=/tmp/numra-e2e-exports \
  uv run python -m numra_api.worker &

# 6. Run the spec (builds and starts the Next.js server itself, port 4180)
cd apps/web && API_INTERNAL_SYSTEM_URL=http://127.0.0.1:8010 \
  npx playwright test --config=playwright.system.config.ts
```

`CORS_ALLOWED_ORIGINS` must match the Next.js port the spec's `webServer` actually
binds (`SYSTEM_E2E_WEB_PORT`, default 4180) — `OriginValidationMiddleware` rejects any
state-changing request whose `Origin` header (forwarded verbatim through the proxy) is
not in that allowlist, independent of CORS itself (which does not apply here at all,
since the browser only ever talks same-origin to the Next.js server; the Origin check
is what actually gates it).

The registration endpoint is IP-rate-limited (5/hour) in front of the same Redis
database — re-running the spec repeatedly against a warm Redis will eventually hit
`RATE_LIMIT_EXCEEDED`; `redis-cli -n 2 FLUSHDB` (or whichever DB index `REDIS_URL`
above points at) between runs during manual iteration.

## What the journey covers, against the live stack

1. Register (direct API call — no registration UI exists) + log in through the real
   UI.
2. Create a person (the pinned golden fixture's birth data — Lukas Springer) and let
   the real deterministic engine compute it. Asserts the pinned golden display values
   (Life Path 22/4, Expression 62/8, Soul Urge 18/9, Personality 44/8) and the real
   Calculation Inspector trace text.
3. Dashboard and Today both load against the live backend.
4. Generates a QUICK report through the real job queue; waits for the real worker to
   claim and complete it (`NUMRA_LLM_PROVIDER=mock`).
5. Exports a real PDF (`POST /v1/exports` blocks on a genuine Playwright/Chromium
   render in the PDF service) and verifies the downloaded bytes start with the real
   `%PDF-` signature.
6. Creates a second person with a current name and preferred name, and verifies the
   Identity Timeline shows all three entries.
7. Compares both people via a real relationship endpoint; asserts the "no compatibility
   percentage" copy is present and that no `%` character appears anywhere in the
   rendered comparison.
8. Delete-All: verifies the session cookie is genuinely rejected afterwards (`401` from
   `GET /v1/auth/me`, not just a client-side redirect) and that the same email can be
   registered again (proof the account row itself is gone, not just its session).
   The exported PDF's physical removal from disk is verified independently, outside
   the spec, directly against the `ExportStorage` directory (`ls
   $EXPORT_STORAGE_DIR` empty after the run) — an authenticated download request
   cannot distinguish "row gone" from "session gone" once both are true, so this is
   checked at the filesystem, not through the API.

## Known, unrelated console noise

A `401` from an eagerly-checked `/api/v1/auth/me` on an unauthenticated page visit and
a `404` for a missing favicon appear in the browser console during the run — both are
the same pre-existing, benign artifacts already documented in
`web-api-proxy-and-csp.md`, not related to anything this spec tests.
