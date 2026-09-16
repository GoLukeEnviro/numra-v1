# MOBILE-12C Native Today/Daily-Brief (read-only)

**Status:** Completed in PR #84, production-verified, and frozen with the native client.

## User story

As a signed-in mobile user, I can see today's personal timing (personal
day/month/year) and the composed daily brief for a selected person, without
the app recomputing any numerology itself, so that AVENYTH's mobile surface
shows the same deterministic content as the web app.

## Scope

Extend the existing, generic, person-scoped, read-only endpoints
`GET /v1/people/{person_id}/timing` and `GET /v1/people/{person_id}/daily-brief`
to also accept the mobile bearer token, alongside their existing cookie auth.
No new backend route, no new computation, no new DB writes.

## Acceptance criteria

- [x] `GET /v1/people/{person_id}/timing` and `GET /v1/people/{person_id}/daily-brief`
  accept `Authorization: Bearer <token>` in addition to the existing
  `numra_session` cookie, via a single combined auth dependency — no new route.
- [x] All other existing routes are unaffected; the bearer boundary stays scoped
  to exactly these two endpoints plus the pre-existing `/v1/auth/mobile/*`.
- [x] Missing, malformed, expired or revoked bearer tokens on these endpoints
  return the existing generic 401 shape (no new error format).
- [x] A bearer-authenticated request for a `person_id` not owned by the caller
  returns the same 404/403 the cookie path already returns (ownership check is
  reused, not reimplemented).
- [x] The mobile client fetches both endpoints with the stored opaque token and
  renders the already-composed `daily-brief` sections (`display_name_de`,
  `display_value`, `text_de`) and the `timing` figures — no numerology math in
  the client.
- [x] Mobile UI covers: loading, ready (with content), no-person-yet,
  transport/config error, and unauthorized (401 → same secure sign-out path
  MOBILE-12B already uses for the auth screens).
- [x] Existing browser cookie/CSRF behavior for `/timing` and `/daily-brief`
  is unchanged.
- [x] OpenAPI and the generated TS schema reflect the updated auth requirement
  (`security` alternatives) for both endpoints.

## Exclusions

Mutations, offline cache, background refresh, push notifications, person
picker/creation in the mobile client (uses the first/only owned person for
this increment), date navigation beyond "today", biometrics, token refresh.
