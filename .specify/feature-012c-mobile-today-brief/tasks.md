# Tasks: MOBILE-12C Native Today/Daily-Brief

## Backend — TDD

- [ ] Write bearer-auth tests for `/timing` and `/daily-brief` (RED).
- [ ] GREEN: `get_current_user_any_auth` in `deps.py`, wired into both routes.
- [ ] Negative tests: missing/malformed/unknown/revoked bearer → generic 401.
- [ ] Ownership test: bearer token, foreign `person_id` → same status as cookie path.
- [ ] Regenerate OpenAPI and TypeScript schema.

## Mobile client — TDD

- [ ] RED: `today-client.ts` tests.
- [ ] GREEN: `today-client.ts` implementation.
- [ ] RED/GREEN: `today-state.ts` reducer + tests (all transitions).
- [ ] Wire into `App.tsx`; unauthorized → existing token-deletion path.

## Integration

- [ ] Run full mobile and web verification.
- [ ] Update `specs/v2/api-contract.md` (auth-extensions bullet + roadmap entry).
- [ ] Review the focused diff and dependency audit.
- [ ] Commit, push and open a stacked PR without merging or deploying.
