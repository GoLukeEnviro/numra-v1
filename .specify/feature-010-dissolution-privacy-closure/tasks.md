# Tasks: WEB-10 Dissolution & Privacy Closure

**Detected Pattern:** Next.js + TypeScript + Vitest/RTL

## User Story 1: Retained relationship history

### Phase 1A: Tests
- [x] Add a failing connection-page test for active-to-dissolved transition and retained workspace link.
- [x] Add a failing connection-page test for an accessible dissolution error.
- [x] Run the focused test and confirm failures are caused by missing behavior.

### Phase 1B: Implementation
- [x] Update connection state from the server response.
- [x] Render a separate historical section with read-only workspace links.
- [x] Add inline mutation error handling and translations.
- [x] Run the focused tests to green.

## User Story 2: Accurate account-deletion disclosure

### Phase 2A: Test
- [x] Add a failing component test for retained/pseudonymized shared-history disclosure.
- [x] Confirm the expected red failure.

### Phase 2B: Implementation
- [x] Update German and English account-deletion copy without changing deletion mechanics.
- [x] Run the focused test to green.

## Global Checkpoints

- [x] Full web quality gates pass.
- [x] Independent review passes.
- [x] Commit and stacked PR are created; no merge or deployment occurs.
