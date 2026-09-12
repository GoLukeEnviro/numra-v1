# WEB-10 Dissolution & Privacy Closure

## User Stories

### User Story 1: Retained relationship history

As a connected user, I want a dissolved connection to remain visible as historical data, so that I can reach the shared artifacts the retention policy keeps read-only.

**Acceptance Criteria:**
- [x] Active and dissolved connections are visually separated.
- [x] A successful dissolution transitions the row into the historical section without a reload.
- [x] A dissolved connection exposes its retained workspace, but no consent or mutation action.
- [x] A failed dissolution remains actionable and displays an accessible error.

### User Story 2: Accurate account-deletion disclosure

As an account owner, I want the destructive confirmation to distinguish deleted private data from retained pseudonymized shared history, so that my consent is informed.

**Acceptance Criteria:**
- [x] The confirmation lists private/account data that is deleted.
- [x] It explicitly explains that policy-retained shared artifacts remain read-only and are pseudonymized where possible.
- [x] Password confirmation and existing deletion behavior remain unchanged.

## Functional Requirements

- FR-1: Use the server-returned `UserConnectionOut` after dissolution as UI authority.
- FR-2: Resolve retained workspace links through the existing workspace list contract.
- FR-3: Never offer consent or dissolution controls for a dissolved connection.
- FR-4: Preserve existing phase-gate behavior and surface mutation errors inline.
- FR-5: Do not change backend, schema, retention, or deletion behavior.

## Non-Functional Requirements

- Accessibility: status and error copy must be available through semantic roles/text.
- Privacy: copy must match `specs/v2/dissolution-policy.md`.
- Compatibility: German and English catalogs remain key-identical.

## Success Criteria

- [x] Focused Vitest tests prove success and error transitions.
- [x] Full web tests, lint, typecheck, build, and relevant E2E pass.
- [x] Independent review has no Critical or Important findings.
