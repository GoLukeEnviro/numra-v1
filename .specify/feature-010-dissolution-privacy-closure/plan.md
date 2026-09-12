# Technical Plan: WEB-10 Dissolution & Privacy Closure

## Detected Stack

- Next.js 15, React 18, TypeScript
- Vitest and React Testing Library in colocated `__tests__`
- Existing API client contracts generated from OpenAPI

## Architecture

Keep the feature inside the existing connections and privacy surfaces. Replace the local removed-id projection with a local connection snapshot updated from the dissolution response. Derive active and historical sections from that snapshot, using the existing workspace lookup for retained-history navigation.

## Contracts

- `GET /v1/connections` supplies active and dissolved connections.
- `POST /v1/connections/{id}/dissolve` returns the authoritative dissolved row.
- `GET /v1/workspaces` maps `connection_id` to retained workspace `id`.
- `POST /v1/account/delete-all` remains unchanged.

## Verification

- `pnpm --filter @numra/web test -- page.test.tsx`
- `pnpm --filter @numra/web test`
- `pnpm --filter @numra/web lint`
- `pnpm --filter @numra/web typecheck`
- `pnpm --filter @numra/web build`
- Relevant Playwright journey
