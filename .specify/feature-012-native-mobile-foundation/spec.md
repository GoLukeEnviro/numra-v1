# PR-V2-12A Native Mobile Foundation

## Purpose

Establish the first bounded native-mobile vertical slice after V2 Core: an Expo app
that proves it can resolve a configured API origin and read the existing public
configuration contract. Authentication, offline sync, push notifications and device
credentials remain explicitly outside this slice because no approved native session
contract exists yet.

## User story

As a mobile user, I can open AVENYTH and see whether the configured service is ready,
so that installation and environment errors are actionable before sign-in is added.

## Acceptance criteria

- [x] The app has loading, ready, misconfigured and unavailable states.
- [x] The API origin comes from `EXPO_PUBLIC_API_URL`, without an embedded production URL.
- [x] Non-local origins must use HTTPS; local development may use HTTP.
- [x] The readiness request uses `GET /v1/config/public` and validates its minimum shape.
- [x] The mobile package has unit tests, type checking and linting.
- [x] Existing web, API and schema behavior remains unchanged.

## Constraints

- `apps/mobile` uses Expo and React Native as required by `specs/v2/architecture.md`.
- No native authentication is implemented until cookie, CSRF and secure-storage
  semantics have an approved contract.
- No new backend route or database migration is introduced.
