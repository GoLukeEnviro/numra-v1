# MOBILE-12B Native Authentication

## User story

As a mobile user, I can sign in, restore my session and sign out without storing my
password, so that AVENYTH can authenticate safely outside a browser cookie jar.

## Acceptance criteria

- [x] Native login returns a single opaque session token and its expiry over HTTPS.
- [x] The raw token is never persisted server-side and is returned only once.
- [x] Native `me` and logout accept `Authorization: Bearer <token>`.
- [x] Missing, malformed, expired or revoked tokens return the existing generic 401 shape.
- [x] Wrong credentials remain indistinguishable from browser login failures.
- [x] Logout revokes only the presented session and requires no CSRF token because the
  bearer credential is not ambient browser authority.
- [x] The mobile client persists only the opaque token in OS secure storage and removes
  it on logout or an authenticated 401.
- [x] Existing browser cookie and CSRF behavior is unchanged.

## Exclusions

Registration, password recovery, biometrics, token refresh, push and general bearer
access to product endpoints are later increments.

