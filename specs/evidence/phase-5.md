# Phase 5 Evidence — Frontend

Built by a delegated build agent working exclusively inside `apps/web/`, then
independently re-verified (every command re-run from scratch) before being committed.

| Item | Status |
|---|---|
| All required routes present (`/login`, `/dashboard`, `/people`, `/people/new`, `/people/[id]`, `/analysis/[calculationId]`, `/relationships`, `/relationships/[id]`, `/settings`, `/settings/privacy`) | PASS |
| Typed API client against generated OpenAPI schema, cookie session + CSRF header | PASS |
| Calculation Inspector renders actual `calculation_trace` operations as readable steps | PASS |
| Diagnostic Life Path visually/structurally distinguished from canonical | PASS (unit test asserts `40/4 != 22/4` from the real golden fixture) |
| Relationship comparison shows match/no-match only — no invented percentage | PASS |
| Dark Premium design system, WCAG AA contrast | PASS (documented ratios in judgment calls below) |
| Loading/empty/error/success states on every data page | PASS |
| Playwright golden journey (login → create profile → see 22/4, 62/8, 18/9, 44/8 → inspect trace) | PASS |
| `eslint --max-warnings 0` | PASS |
| `tsc --noEmit` | PASS |
| Production build (`next build`) | PASS — all 11 routes compiled |
| Vitest unit tests | PASS — 7/7 |

## Commands independently re-run for verification (not just trusted from the agent's report)

```text
$ pnpm --filter @numra/web lint
> eslint . --max-warnings 0
(no output = clean)

$ pnpm --filter @numra/web exec tsc --noEmit
(no output = clean)

$ pnpm --filter @numra/web test -- --run
Test Files  2 passed (2)
     Tests  7 passed (7)

$ pnpm --filter @numra/web build
✓ Compiled successfully
Route (app): / /_not-found /analysis/[calculationId] /dashboard /login /people
  /people/[id] /people/new /relationships /relationships/[id] /settings /settings/privacy
(11 app routes + not-found, all compiled)

$ pnpm --filter @numra/web exec playwright test
✓  1 [chromium] › e2e/golden-journey.spec.ts (1.2s)
1 passed (27.3s)
```

## Judgment calls made explicit (from the delegated agent's own report, spot-checked)

- **No "list calculations"/"list relationships" endpoint exists** in the Phase 2 API
  (`PersonOut` carries no "latest calculation" pointer, and there is no
  `GET /v1/relationships` list route). Rather than inventing a server capability, the
  app tracks calculation/relationship ids it has *seen* in `localStorage`
  (`src/lib/local-calculations.ts`, `src/lib/local-relationships.ts`) purely as a
  navigation convenience — every calculation is always re-fetched from the API when
  opened, never trusted from the cache. This is a reasonable, low-risk judgment call
  that does not fabricate any numerology data.
- **UI language is English**, not German — the OpenAPI contract and this delegated
  task's brief are both English; this diverges from the CLAUDE.md governance file found
  in the sandbox environment, which the agent correctly identified as describing an
  unrelated, pre-existing repository, not this NUMRA V1 build.
- **shadcn/ui primitives hand-built** (Button, Input, Select, Card, Badge, Tabs, states)
  in the shadcn idiom using `class-variance-authority` + `tailwind-merge`, without
  pulling in Radix UI primitives — reduces dependency surface/install risk for a
  from-scratch build; functionally equivalent for this app's needs.
- **Contrast pairs were computed, not assumed**: `plum` (#604B72) on the dark
  `background` token is only ~2.6:1 (fails AA even at large text), so it is used solely
  as a *filled badge surface* with ivory text (~6.5:1) rather than as text-on-background.
  `bronze` is reserved for large/decorative elements (borders, the SVG numeric-wheel
  motif, headings); `gold`/`ivory` carry body and interactive text at 8–9:1.
- **Playwright's `webServer` rebuilds against its own origin** (`NEXT_PUBLIC_API_BASE_URL`
  pointed at `http://127.0.0.1:4173`) purely for the e2e run, to avoid CORS-preflight
  mocking complexity when fully intercepting API calls with `page.route()`. The default
  `pnpm build` target is unaffected and still points at the real dev API contract
  (`http://localhost:8000`).
- **`/people/[id]` gained a working "Delete profile" action** (backed by the real
  `DELETE /v1/people/{id}` endpoint) as a natural completion of the CRUD surface, beyond
  the originally listed flows. Account-level deletion on `/settings/privacy` was left as
  a disabled/placeholder control at the time this phase was built, since
  `POST /v1/account/delete-all` did not exist yet — it was added immediately afterward
  in this same Phase 6 commit (see below); wiring the privacy page's delete button up to
  the real endpoint is noted as follow-up work, not yet done.

## Not yet built (deferred)

- The privacy page's "Delete all my data" button is not yet wired to the real
  `POST /v1/account/delete-all` endpoint (that endpoint didn't exist when this phase was
  built; it was added in the same Phase 6 work that produced this evidence file).
- `/reports` and `/reports/[id]` (report viewing UI) and PDF export — explicitly out of
  scope for Phase 5 per the delegation brief; Phase 4's report pipeline has no frontend
  yet.
