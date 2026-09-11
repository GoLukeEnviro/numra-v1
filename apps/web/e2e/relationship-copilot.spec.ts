import { expect, test, type Page, type Route } from "@playwright/test";

const USER = { id: "user-1", email: "lukas@example.com", role: "USER", is_active: true };
const WORKSPACE = { id: "workspace-1", connection_id: "connection-1", status: "ACTIVE", relationship_type: "PARTNER", created_at: "2026-09-11T12:00:00Z", dissolved_at: null };
const OVERVIEW = { workspace: WORKSPACE, dual_profile: [{ user_id: "user-1", display_name: "Lukas", self_person: null, core_numbers: null }, { user_id: "user-2", display_name: "Ada", self_person: null, core_numbers: null }] };
const SHARED_THREAD = { id: "thread-shared", workspace_id: WORKSPACE.id, owner_user_id: null, scope: "RELATIONSHIP_SHARED", context_version: 1, created_at: "2026-09-11T12:00:00Z", archived_at: null };
const PRIVATE_THREAD = { ...SHARED_THREAD, id: "thread-private", owner_user_id: USER.id, scope: "RELATIONSHIP_PRIVATE" };

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

function message(id: string, threadId: string, role: "USER" | "ASSISTANT", content: string, basisType: string | null) {
  return { id, thread_id: threadId, role, status: "COMPLETE", author_user_id: role === "USER" ? USER.id : null, content, basis_type: basisType, prompt_version: "numra-copilot-v1", knowledge_version: "copilot-v1", context_snapshot_id: "snapshot-1", model_provider: "mock", model_name: "mock-1", error_code: null, created_at: "2026-09-11T12:01:00Z" };
}

async function mockCopilot(page: Page) {
  await page.route("**/v1/auth/me", (route) => json(route, USER));
  await page.route("**/v1/people", (route) => json(route, []));
  await page.route("**/v1/connections", (route) => json(route, [{ id: "connection-1", counterpart_user_id: "user-2", counterpart_display_name: "Ada", status: "ACTIVE", created_at: "2026-09-11T12:00:00Z", dissolved_at: null }]));
  await page.route("**/v1/workspaces", (route) => json(route, [WORKSPACE]));
  await page.route("**/v1/workspaces/workspace-1", (route) => json(route, OVERVIEW));
  await page.route("**/v1/workspaces/workspace-1/copilot/threads", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON() as { scope: string };
      await json(route, body.scope === "RELATIONSHIP_PRIVATE" ? PRIVATE_THREAD : SHARED_THREAD);
      return;
    }
    await json(route, [SHARED_THREAD]);
  });
  await page.route("**/v1/workspaces/workspace-1/copilot/threads/*/messages**", async (route) => {
    const privateThread = route.request().url().includes("thread-private");
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON() as { content: string };
      await json(route, {
        user_message: message("private-user", "thread-private", "USER", body.content, null),
        assistant_message: message("private-assistant", "thread-private", "ASSISTANT", "Dafür liegen noch nicht genügend Daten vor.", "INSUFFICIENT_EVIDENCE"),
      });
      return;
    }
    await json(route, privateThread ? [] : [message("shared-assistant", "thread-shared", "ASSISTANT", "Gemeinsame Beobachtung", "OBSERVED_WORKSPACE_DATA")]);
  });
}

for (const [name, viewport] of Object.entries({ desktop: { width: 1440, height: 900 }, mobile: { width: 390, height: 844 } })) {
  test(`relationship copilot keeps shared and private conversations separate on ${name}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await mockCopilot(page);
    await page.goto("/workspaces/workspace-1/copilot");

    await expect(page.getByRole("heading", { name: "Beziehungs-Copilot" })).toBeVisible();
    await expect(page.getByText("Gemeinsame Beobachtung")).toBeVisible();
    await expect(page.getByText("Beobachtete Workspace-Daten")).toBeVisible();

    await page.getByRole("button", { name: "Privat" }).click();
    await expect(page.getByText(/Dein Partner sieht weder deine Fragen noch die Antworten/)).toBeVisible();
    await expect(page.getByText("Gemeinsame Beobachtung")).not.toBeVisible();
    await page.getByLabel("Nachricht").fill("Was ist belastbar?");
    await page.getByRole("button", { name: "Senden", exact: true }).click();

    await expect(page.getByText("Dafür liegen noch nicht genügend Daten vor.")).toBeVisible();
    await expect(page.getByText("Noch keine ausreichende Datengrundlage")).toBeVisible();
  });
}
