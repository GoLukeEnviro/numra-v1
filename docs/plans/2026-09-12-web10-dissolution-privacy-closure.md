# WEB-10 Dissolution & Privacy Closure Implementation Plan

> **For Claude:** Use `${SUPERPOWERS_SKILLS_ROOT}/skills/collaboration/executing-plans/SKILL.md` to implement this plan task-by-task.

**Goal:** Close the missing WEB-10 frontend increment with retained dissolution history and accurate account-deletion disclosure.

**Architecture:** Keep server state authoritative: the dissolve response replaces the connection row locally, while the existing workspace listing resolves the retained-history destination. Account deletion mechanics stay untouched; only the confirmation copy is aligned with the frozen retention policy.

**Tech Stack:** Next.js 15, React 18, TypeScript, Vitest, React Testing Library, Playwright

---

### Task 1: Dissolution state transition

**Files:**
- Modify: `apps/web/src/app/connections/page.tsx`
- Test: `apps/web/src/app/connections/__tests__/page.test.tsx`

1. Write a test that dissolves an active connection and expects it under historical connections with a workspace link.
2. Run the focused Vitest file and confirm RED because the row currently disappears.
3. Replace removed-id state with authoritative connection-row state.
4. Render active and dissolved collections separately.
5. Run the focused test and confirm GREEN.

### Task 2: Dissolution failure

**Files:**
- Modify: `apps/web/src/app/connections/page.tsx`
- Modify: `apps/web/src/i18n/messages/de/app.ts`
- Modify: `apps/web/src/i18n/messages/en/app.ts`
- Test: `apps/web/src/app/connections/__tests__/page.test.tsx`

1. Write a test that rejects the dissolve request and expects an alert while retaining the row.
2. Run the test and confirm RED because errors are currently unhandled.
3. Add inline accessible error state and localized fallback copy.
4. Run the test and confirm GREEN.

### Task 3: Account-deletion disclosure

**Files:**
- Modify: `apps/web/src/i18n/messages/de/app.ts`
- Modify: `apps/web/src/i18n/messages/en/app.ts`
- Test: `apps/web/src/components/settings/__tests__/delete-account-panel.test.tsx`

1. Write a rendered-component test that opens confirmation and expects the retained, pseudonymized shared-history disclosure.
2. Run the focused test and confirm RED because the copy is absent.
3. Add a dedicated disclosure message and render it in the destructive confirmation.
4. Run the focused test and confirm GREEN.

### Task 4: Verify and publish

1. Run all web tests, lint, typecheck, build, and relevant Playwright coverage.
2. Request independent review and address Critical/Important findings.
3. Commit on `codex/web10-dissolution-privacy-closure`.
4. Push and create a stacked PR targeting `codex/web11-evidence-layer-ui`.
5. Wait for CI; do not merge or deploy while the documented deployment halt remains.
