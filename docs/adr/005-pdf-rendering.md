# ADR 005 — Internal Playwright/Chromium PDF Service, Not a Public URL Renderer

## Status

Accepted.

## Context

A "render this URL to PDF" service is a classic SSRF vector: if a caller can supply an
arbitrary URL, an internal service becomes a proxy into private network space. NUMRA
needs print-quality PDF output of already-generated report JSON, not a general-purpose
web-page-to-PDF tool.

## Decision

`apps/pdf` is a small internal-only Express service with exactly one meaningful route,
`POST /render/report`. It never navigates to a caller-supplied URL — it only ever calls
`page.setContent(html)` on HTML built in-process (`template.js`) from a JSON payload the
caller already fetched from the NUMRA API. Access requires a static bearer token
(`PDF_INTERNAL_TOKEN`) the service refuses to start without. Web and PDF share the same
underlying `StructuredReport` data shape so visual parity is a template-consistency
concern, not a data-shape one (master prompt §130).

## Consequences

- No URL-based SSRF surface exists in this service by construction — there is nothing
  to disable or sandbox because there is no URL parameter at all.
- The service is easy to test deterministically: fixed JSON in, byte-checkable PDF out
  (verified: `%PDF-` header, non-trivial size, at least one `/Type /Page` object,
  expected headings present in the rendered DOM before printing — see
  `apps/pdf/src/__tests__/render.test.js`).
- The service must be network-isolated from the public internet in production (internal
  Docker network only, no public port mapping) — the bearer token is defense-in-depth,
  not a substitute for network isolation.
