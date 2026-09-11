import { expect, test, type Page, type Route } from "@playwright/test";

const USER = { id: "user-1", email: "lukas@example.com", role: "USER", is_active: true };
const ACTIVE = { id: "workspace-1", connection_id: "conn-1", status: "ACTIVE", relationship_type: "PARTNER", created_at: "2026-08-20T09:00:00Z", dissolved_at: null };
const DISSOLVED = { ...ACTIVE, status: "DISSOLVED", dissolved_at: "2026-09-09T09:00:00Z" };
const MEMBERS = [{ user_id: "user-1", display_name: "Lukas Springer", self_person: null, core_numbers: null }, { user_id: "user-2", display_name: "Ada Lovelace", self_person: null, core_numbers: null }];
const ACTIVE_TASK = { id: "task-active", workspace_id: "workspace-1", task_type: "JOINT_SHARED", status: "ACTIVE", proposer_user_id: "user-1", recipient_user_id: null, title: "Gemeinsam einen freien Abend planen", description: "Handys weglegen und bewusst Zeit füreinander reservieren.", due_date: "2026-09-18", completed_at: null, source_analysis_id: null, prompt_version: null, knowledge_version: null, roadmap_milestone_id: null, created_at: "2026-09-10T09:00:00Z", updated_at: "2026-09-10T09:00:00Z" };
const PROPOSAL = { ...ACTIVE_TASK, id: "task-proposal", task_type: "FOR_PARTNER_PROPOSED", status: "PROPOSED", proposer_user_id: "user-2", recipient_user_id: "user-1", title: "Sonntag zusammen spazieren gehen", description: "Eine Stunde ohne feste Agenda." };
const COMPLETED = { ...ACTIVE_TASK, id: "task-completed", status: "COMPLETED", title: "Wochenplanung abstimmen", completed_at: "2026-09-09T10:00:00Z" };

async function json(route: Route, body: unknown) { await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) }); }
async function setup(page: Page, size: { width: number; height: number }, workspace: typeof ACTIVE | typeof DISSOLVED, tasks: unknown[]) {
  await page.setViewportSize(size);
  await page.route("**/v1/auth/me", (route) => json(route, USER));
  await page.route("**/v1/connections", (route) => json(route, []));
  await page.route("**/v1/workspaces", (route) => route.request().url().endsWith("/v1/workspaces") ? json(route, [workspace]) : route.continue());
  await page.route("**/v1/workspaces/workspace-1", (route) => json(route, { workspace, dual_profile: MEMBERS }));
  await page.route("**/v1/workspaces/workspace-1/tasks?*", (route) => json(route, tasks));
  await page.route("**/v1/workspaces/workspace-1/tasks/task-proposal/accept", (route) => json(route, { ...PROPOSAL, status: "ACTIVE" }));
}

for (const [name, size] of Object.entries({ desktop: { width: 1440, height: 900 }, mobile390: { width: 390, height: 844 } })) {
  test(`tasks -- active and incoming -- ${name}`, async ({ page }) => {
    await setup(page, size, ACTIVE, [PROPOSAL, ACTIVE_TASK, COMPLETED]);
    await page.goto("/workspaces/workspace-1/tasks");
    await expect(page.getByRole("button", { name: "Annehmen" })).toBeVisible();
    await expect(page.getByText("Gemeinsam einen freien Abend planen")).toBeVisible();
    await page.getByRole("button", { name: "Annehmen" }).click();
    await expect(page.getByRole("button", { name: "Als erledigt markieren" })).toHaveCount(2);
    await page.screenshot({ path: `test-results/pr-web-07/tasks-active-${name}.png`, fullPage: true });
  });
  test(`tasks -- create proposal -- ${name}`, async ({ page }) => {
    await setup(page, size, ACTIVE, []);
    await page.goto("/workspaces/workspace-1/tasks");
    await page.getByRole("button", { name: "Aufgabe anlegen" }).click();
    await page.getByLabel("Aufgabentyp").selectOption("FOR_PARTNER_PROPOSED");
    await page.getByLabel("Titel").fill("Mehr gemeinsame Zeit");
    await expect(page.getByText(/ausdrücklich annehmen/)).toBeVisible();
    await page.screenshot({ path: `test-results/pr-web-07/tasks-create-${name}.png`, fullPage: true });
  });
  test(`tasks -- dissolved history -- ${name}`, async ({ page }) => {
    await setup(page, size, DISSOLVED, [COMPLETED]);
    await page.goto("/workspaces/workspace-1/tasks");
    await expect(page.getByRole("heading", { name: "Historische Ansicht" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Aufgabe anlegen" })).toHaveCount(0);
    await page.screenshot({ path: `test-results/pr-web-07/tasks-dissolved-${name}.png`, fullPage: true });
  });
}
