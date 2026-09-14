# Plan: MOBILE-12C Native Today/Daily-Brief

## Backend (TDD)

1. **RED**: add a unit/integration test that calls `GET /v1/people/{id}/timing`
   and `GET /v1/people/{id}/daily-brief` with a valid mobile bearer token and
   expects 200 — fails today (cookie-only).
2. **GREEN**: in `apps/api/src/numra_api/deps.py`, add
   `get_current_user_any_auth` — tries the `Authorization` header first
   (reusing `get_current_bearer_session`/`get_current_bearer_user`'s lookup),
   falls back to the `numra_session` cookie
   (`get_current_session`/`get_current_user`) when no header is present.
   Reuse the existing session/user resolution helpers; do not duplicate
   lookup logic. Swap this dependency into
   `get_timing_route`/`get_daily_brief_route` in
   `apps/api/src/numra_api/routes/calculations.py` only.
3. Negative tests mirroring `test_mobile_auth.py`'s
   `test_mobile_bearer_rejects_missing_malformed_and_unknown_tokens`: missing
   header, malformed header, unknown token, revoked token → 401 generic shape,
   on both endpoints.
4. Ownership test: bearer token for user A, `person_id` owned by user B → same
   status code the cookie path already returns for that case (verify via
   existing test for the cookie path first, then mirror with bearer).
5. Regenerate OpenAPI (`security` alternatives on both operations) and the
   generated TS schema; no other contract fields change.

## Mobile client (TDD)

1. **RED**: write tests for a small `today-client.ts` (`getTiming`,
   `getDailyBrief`) that attaches `Authorization: Bearer <token>` the same way
   `auth-client.ts` does — fails, module doesn't exist.
2. **GREEN**: implement `apps/mobile/src/api/today-client.ts`. Reuse the same
   inline bearer-header pattern as `auth-client.ts` (no premature abstraction
   into a generic fetch wrapper unless a third consumer appears).
3. **RED/GREEN**: `apps/mobile/src/screens/today-state.ts` — a pure reducer
   mirroring `auth-state.ts`'s shape: states `loading | ready (+timing +brief)
   | noPerson | error (+message) | unauthorized`; actions
   `loaded | failed | noPerson | unauthorized`. On `unauthorized`, the caller
   (not the reducer) triggers the existing token-deletion path already used
   by `auth-client.ts` on an authenticated 401.
4. Wire into `App.tsx`: once `authReducer` reaches `signedIn`, fetch the first
   owned person (reuse `apps/mobile/src/api` conventions; if no people exist,
   `noPerson` state — a simple message, no create-person flow), then today's
   timing + daily-brief for that person, rendered as a minimal list (no design
   system work beyond what `App.tsx` already has).
5. Component/reducer tests for every state transition, matching the density of
   `auth-state.test.ts`.

## Docs

- `specs/v2/api-contract.md`: add a short "Auth extensions" bullet noting the
  bearer boundary now also covers `/v1/people/{id}/timing` and
  `/v1/people/{id}/daily-brief`, and add an entry under the PR roadmap for
  MOBILE-12C.
- `docs/planning/avenyth-web-execution-state.md`: update after merge, same
  pattern as prior increments.

## Order

deps.py auth-dependency (RED→GREEN) → route wiring → negative/ownership tests →
OpenAPI/schema regen → mobile `today-client.ts` (RED→GREEN) →
`today-state.ts` reducer (RED→GREEN) → `App.tsx` wiring → mobile tests →
docs → full verification → PR → independent review → CI → merge → post-merge
CI verify.
