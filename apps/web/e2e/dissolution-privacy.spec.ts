import { expect, test, type Page, type Route } from "@playwright/test";

const USER = { id: "user-1", email: "me@example.com", role: "USER", is_active: true };
const ACTIVE = { id: "conn-1", counterpart_user_id: "user-2", counterpart_display_name: "Ada Lovelace", status: "ACTIVE", created_at: "2026-09-01T00:00:00Z", dissolved_at: null };
const WORKSPACE = { id: "ws-1", connection_id: "conn-1", status: "ACTIVE", relationship_type: "PARTNER", created_at: "2026-09-01T00:00:00Z", dissolved_at: null };

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

async function mockSession(page: Page) {
  await page.route("**/v1/auth/me", (route) => json(route, USER));
}

test("dissolution keeps the retained workspace reachable", async ({ page }) => {
  await mockSession(page);
  await page.route("**/v1/connections", (route) => json(route, [ACTIVE]));
  await page.route("**/v1/connections/invitations", (route) => json(route, []));
  await page.route("**/v1/workspaces", (route) => json(route, [WORKSPACE]));
  await page.route("**/v1/connections/conn-1/dissolve", (route) => json(route, { ...ACTIVE, status: "DISSOLVED", dissolved_at: "2026-09-12T10:00:00Z" }));

  await page.goto("/connections");
  await page.getByRole("button", { name: "Verbindung auflösen" }).click();
  await page.getByRole("button", { name: "Endgültig auflösen" }).click();

  await expect(page.getByRole("heading", { name: "Historische Verbindungen" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Historischen Workspace öffnen" })).toHaveAttribute("href", "/workspaces/ws-1");
});

test("account deletion discloses retained pseudonymized shared history", async ({ page }) => {
  await mockSession(page);
  await page.goto("/settings/privacy");
  await page.getByRole("button", { name: "Mein Konto löschen" }).click();

  await expect(page.getByText(/Gemeinsam erzeugte historische Inhalte/)).toContainText("pseudonymisiert");
});
