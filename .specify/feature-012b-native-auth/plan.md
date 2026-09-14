# Technical Plan: MOBILE-12B Native Authentication

- Add dedicated `/v1/auth/mobile/login`, `/me` and `/logout` routes.
- Reuse the existing random session token generator, SHA-256 token hashing, sessions
  table, TTL, disabled-user checks and login rate limit.
- Do not introduce JWT, refresh tokens, CSRF exceptions on existing routes or schema
  migrations.
- Add `expo-secure-store`; isolate persistence behind a small injectable session store.
- Test API integration first, then the TypeScript client/session store, then UI state.

Threat boundary: bearer tokens are possession credentials and must only cross HTTPS.
They are not cookies, so the browser-oriented double-submit CSRF mechanism does not
apply to the dedicated logout route. Logs and error payloads must never contain them.

