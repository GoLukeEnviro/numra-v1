# Tasks: MOBILE-12C Native Today/Daily-Brief

## Backend — TDD

- [x] Write bearer-auth tests for `/timing` and `/daily-brief` (RED).
- [x] GREEN: `get_current_user_any_auth` in `deps.py`, wired into both routes.
- [x] Negative tests: missing/malformed/unknown/revoked bearer → generic 401.
- [x] Ownership test: bearer token, foreign `person_id` → same status as cookie path.
- [x] Regenerate OpenAPI and TypeScript schema.

## Mobile client — TDD

- [x] RED: `today-client.ts` tests.
- [x] GREEN: `today-client.ts` implementation.
- [x] RED/GREEN: `today-state.ts` reducer + tests (all transitions).
- [x] Wire into `App.tsx`; unauthorized → existing token-deletion path.

## Integration

- [x] Run full mobile and web verification.
- [x] Update `specs/v2/api-contract.md` (auth-extensions bullet + roadmap entry).
- [x] Review the focused diff and dependency audit.
- [ ] Commit, push and open a stacked PR without merging or deploying.
