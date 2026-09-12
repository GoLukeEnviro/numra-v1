# Technical Plan: PR-V2-12A Native Mobile Foundation

## Stack

- Expo SDK 57 / React Native 0.86 / React 19, with React type declarations kept on
  the repository's existing React-18 line to avoid leaking incompatible global JSX
  declarations into the Next workspace
- TypeScript
- Vitest for environment and API-boundary tests

## Design

1. Add `apps/mobile` to the pnpm workspace.
2. Isolate origin resolution and public-config validation in `src/api/public-config.ts`.
3. Render the four launch states from `App.tsx` with a retry action for transport errors.
4. Keep the slice unauthenticated. The current API issues HttpOnly cookies and requires
   a CSRF cookie/header for mutations; changing that is a separate security decision.

## Verification

- Focused RED/GREEN tests
- Mobile test, lint and TypeScript commands
- Existing web test, lint, typecheck and build gates
