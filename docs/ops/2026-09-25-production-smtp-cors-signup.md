# Production SMTP + CORS + Self-Signup activation (2026-09-25/26)

Issue: [#193](https://github.com/GoLukeEnviro/numra-v1/issues/193)

## Summary

Email delivery on `numra-prod` was structurally disabled: `EMAIL_BACKEND` and
all `SMTP_*` variables were unset in `/etc/numra/numra.env`, even though
`compose.production.yml` already mapped them into the `api` and `worker`
services. This phase brought production SMTP, self-signup, and CORS into a
working, end-to-end-verified state.

## What changed (host-only, not in this repo)

All of the following live in `/etc/numra/numra.env` on the production host
(agent0), which is **never committed to git** and mode `600`. This repo only
carries the compose file that references these variables (see
[`deploy/compose.production.yml`](../../deploy/compose.production.yml)).

1. **SMTP credentials** — `EMAIL_BACKEND=smtp`, `SMTP_HOST=smtp.resend.com`,
   `SMTP_PORT=587`, `SMTP_USERNAME=resend`, `SMTP_PASSWORD=<Resend API key>`,
   `SMTP_FROM_EMAIL=no-reply@mail.avenyth.de`, `SMTP_FROM_NAME=AVENYTH`,
   `SMTP_STARTTLS=true`, `WEB_APP_BASE_URL=https://avenyth.de`. The key was
   entered directly on the host via a non-echoing prompt
   (`/opt/numra/scripts/write-smtp-secret.sh`), never through chat or an
   agent tool call.
2. **`ALLOW_SELF_SIGNUP=true`** — was `false`; needed to expose the
   registration form and let the delivery flow be exercised at all.
3. **`CORS_ALLOWED_ORIGINS`** — was
   `["https://agent0-1.taile6801f.ts.net:8443"]` only (Tailscale-only access),
   which made every `POST /v1/auth/register` from the public site fail with
   `403 ORIGIN_NOT_ALLOWED`. Extended to:
   `["https://agent0-1.taile6801f.ts.net:8443","https://avenyth.de","https://www.avenyth.de"]`.
   No wildcard, no `http://`, no other hosts.

Each change was preceded by a timestamped backup of `numra.env`
(`numra.env.bak-pre-smtp-*`, `numra.env.bak-pre-signup-go-*`,
`numra.env.bak-pre-cors-*`, all mode `600`), and only the `api` service was
recreated (`--no-deps --force-recreate`, no image rebuild, no `git pull`) —
`worker`, `pdf`, and `web` were untouched.

## Verification performed

- Structural check inside the running `api` container: `EMAIL_BACKEND`,
  `SMTP_HOST`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` all set — values never
  printed.
- `OPTIONS /api/v1/auth/register` preflight from both `https://avenyth.de`
  and `https://www.avenyth.de` returns `200` with a matching
  `Access-Control-Allow-Origin`.
- `GET /api/v1/public/config` reports `self_signup_enabled: true`.
- End-to-end, performed by the operator in the browser (not automated by any
  agent): register → "resend verification" banner → email from
  `AVENYTH <no-reply@mail.avenyth.de>` received → verify link opened →
  `/api/v1/auth/me` returns `200`, "email confirmed" shown in settings.

## Known follow-ups

- A test account `cors-probe@invalid.example` may exist unverified in the
  production database; cleanup deferred, not yet confirmed to actually
  exist.
- `health_check.json` 404 and a related service-worker fetch error were
  observed in the browser during this phase — tracked separately in
  [#212](https://github.com/GoLukeEnviro/numra-v1/issues/212), unrelated to
  mail delivery.
- Whether `ALLOW_SELF_SIGNUP` should stay `true` long-term is a product
  decision, not part of this ops phase.
