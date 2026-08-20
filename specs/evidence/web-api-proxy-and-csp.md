# Web/API proxy + frontend security headers — evidence

Part of the "FINAL COMPLETION, PRODUCTION HARDENING" directive, P1 item 8/11
(web→API runtime config + CSP/security headers).

## What changed

- **Same-origin API proxy** (`apps/web/src/app/api/[...path]/route.ts`): the browser
  only ever calls `/api/*`. A Next.js Route Handler (not `next.config.mjs`'s
  `rewrites()`) forwards each request to `API_INTERNAL_URL`, a plain (non-
  `NEXT_PUBLIC_`) env var read fresh on every request.
- **Why not `rewrites()`**: confirmed by inspecting the built
  `.next/routes-manifest.json` that `rewrites()`'s destination is evaluated once at
  `next build` and baked into the manifest — an env var read there is NOT
  reconfigurable at `next start`/container-start time, which was the entire point of
  this change (one built image, runtime-configurable backend). The Route Handler's
  function body genuinely runs per-request in the Node.js runtime.
- **Security headers** (`apps/web/next.config.mjs`): `Content-Security-Policy`,
  `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`
  on every page response (excluded from `/api/*`, which are JSON responses forwarded
  from the FastAPI backend and already carry their own security headers).
- **CSP does not use a nonce/`strict-dynamic`**: this was attempted first (the
  App-Router-documented pattern, via `middleware.ts` generating a per-request nonce)
  and verified, with a real headless-Chromium load, to break the app entirely — every
  script on the page, including Next.js 14.2.35's own inline hydration/RSC bootstrap
  scripts, was blocked by the browser (`Refused to execute inline script... nonce
  required`). The final CSP uses `script-src 'self' 'unsafe-inline'` instead: it still
  blocks any script loaded from a different origin (the SSRF/supply-chain-relevant
  protection), while inline scripts remain exclusively Next.js's own generated
  payload — never user-controlled content, since React escapes all rendered data.

## Real verification performed (not simulated)

Both a real Postgres-backed FastAPI instance (`NUMRA_LLM_PROVIDER=mock`) and a real
`apps/pdf` instance were running locally; the web app was built (`pnpm build`) and
started as its actual `output: "standalone"` server
(`node .next/standalone/apps/web/server.js`) with `API_INTERNAL_URL` pointed at the
live API, static assets copied alongside it exactly as `docker/web.Dockerfile` does.

1. `curl http://127.0.0.1:3000/api/v1/health/ready` → proxied through to the real
   backend, returned `{"status":"healthy","database":"healthy","numerology_engine":
   "healthy","llm":"healthy","pdf":"healthy"}` — full round trip through the Route
   Handler proxy to a real DB/LLM/PDF-backed health check.
2. Loaded `/login` in real headless Chromium (Playwright, the sandbox's installed
   Chromium) with the nonce/`strict-dynamic` CSP: **9 CSP violations**, page never
   hydrated (`.fill()` on the email field did not update React state). This confirmed
   the nonce approach as a genuine "breaks rendering" regression before it could reach
   the user, exactly the failure mode the directive warned against.
3. Same load with the corrected static CSP: **0 CSP violations**, `curl`-confirmed CSP
   header present, `.fill()` round-tripped correctly (proving hydration succeeded).
4. Full real login round trip in the browser: filled the login form, submitted,
   observed a real `POST /api/v1/auth/login` → `200` with the real user JSON, a client
   -side redirect to `/dashboard`, and both `numra_session` and `numra_csrf` cookies
   set in the browser's cookie jar (proving the Route Handler's `Set-Cookie` handling —
   using `getSetCookie()` rather than the header's collapsed string form — correctly
   forwards multiple cookies from one upstream response). A subsequent
   `fetch("/api/v1/auth/me", {credentials:"include"})` from within the page returned
   `200` with the authenticated user, proving the browser's session cookie flows back
   through the proxy on the next request exactly as it would against a real
   deployment.
5. Confirmed the `Origin`/`Referer` header the browser sends is forwarded verbatim by
   the proxy (not stripped, not replaced) — the API's `OriginValidationMiddleware`
   saw the real browser origin (`http://localhost:3000`) and the request passed the
   API's existing `cors_allowed_origins` check unmodified; no change to that
   middleware or its configuration was needed.

## Known follow-up (not part of this item)

One unrelated console error observed during the above (a `401` from an
eagerly-checked `/api/v1/auth/me` on an unauthenticated `/login` visit) is a
pre-existing UX artifact, not a CSP or proxy regression — the auth context's initial
"am I logged in?" probe on an anonymous visit; left as-is since a 401 there is the
expected, correct response, not a bug.

The second console error this originally documented (a `404` for a missing favicon)
turned out to share its root cause with a real Docker build failure: `apps/web/public`
did not exist anywhere in the repository at all, which also breaks
`docker/web.Dockerfile`'s `COPY --from=build /repo/apps/web/public ./apps/web/public`
step outright. Fixed for both by adding `apps/web/public/robots.txt` (a private,
auth-gated app with nothing that should ever be crawled) and a Next.js
App-Router-convention `apps/web/src/app/icon.svg`, which Next.js serves automatically
as the favicon without anything needed in `public/`.
