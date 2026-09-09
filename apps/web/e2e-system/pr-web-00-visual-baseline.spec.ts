import { test, expect, type Page, type Route } from "@playwright/test";

/**
 * Screenshot generator for the human reality-check on PR-WEB-00 (V2-Web-Grundgerüst).
 * Deliberately kept out of system-journey.spec.ts -- this mocks every API call with
 * page.route() (no real backend needed, same pattern as e2e/golden-journey.spec.ts)
 * and runs under playwright.visual-baseline.config.ts, not the default or system
 * config. Every screenshot lands under test-results/pr-web-00/.
 *
 * Page-level states (a)-(e) are captured across all four viewports the blueprint
 * specifies. The isolated component demos this file used to screenshot via an
 * unauthenticated /dev/pr-web-00-demo route (PhaseDisabledState x5, ConsentBadge/
 * ConsentList, WorkspaceSwitcher) are covered instead by Vitest/RTL component tests
 * (see components/ui/__tests__/states.test.tsx and
 * components/consent/__tests__/consent-badge.test.tsx) -- that dev-only route was
 * removed as an unauthenticated app route.
 */

const USER = { id: "user-1", email: "lukas@example.com", role: "USER", is_active: true };
const PERSON = {
  id: "11111111-1111-1111-1111-111111111111",
  birth_first_names: "Lukas",
  birth_middle_names: null,
  birth_last_name: "Springer",
  birth_date: "1986-07-18",
  birth_time: null,
  birth_place: null,
  current_first_names: null,
  current_middle_names: null,
  current_last_name: null,
  preferred_name: null,
  created_at: "2026-08-19T09:00:00Z",
  updated_at: "2026-08-19T09:00:00Z",
};

async function fulfillJson(route: Route, status: number, body: unknown) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

async function mockAuthenticatedApi(page: Page) {
  await page.route("**/v1/auth/me", (route) => fulfillJson(route, 200, USER));
  await page.route("**/v1/people", (route) => fulfillJson(route, 200, [PERSON]));
}

const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  tablet: { width: 768, height: 1024 },
  mobile390: { width: 390, height: 844 },
  mobile430: { width: 430, height: 932 },
} as const;

async function shoot(page: Page, name: string) {
  await page.screenshot({ path: `test-results/pr-web-00/${name}.png`, fullPage: true });
}

for (const [viewportName, size] of Object.entries(VIEWPORTS)) {
  test(`(a) dashboard with V2 sidebar nav -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuthenticatedApi(page);
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Numerologie, die du nachprüfen kannst" })).toBeVisible();
    await shoot(page, `dashboard-nav-${viewportName}`);
  });

  test(`(c) /connections placeholder -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuthenticatedApi(page);
    await page.goto("/connections");
    await expect(page.getByText("Verbindungen kommen bald")).toBeVisible();
    await shoot(page, `connections-placeholder-${viewportName}`);
  });

  test(`(d) /workspaces placeholder -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuthenticatedApi(page);
    await page.goto("/workspaces");
    await expect(page.getByText("Workspaces kommen bald")).toBeVisible();
    await shoot(page, `workspaces-placeholder-${viewportName}`);
  });

  test(`(e) /copilot placeholder -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuthenticatedApi(page);
    await page.goto("/copilot");
    await expect(page.getByText("Copilot kommt bald")).toBeVisible();
    await shoot(page, `copilot-placeholder-${viewportName}`);
  });
}

for (const viewportName of ["mobile390", "mobile430"] as const) {
  test(`(b) mobile bottom nav + "More" sheet open -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(VIEWPORTS[viewportName]);
    await mockAuthenticatedApi(page);
    await page.goto("/dashboard");
    await page.getByRole("button", { name: /Mehr/ }).click();
    await expect(page.getByRole("dialog", { name: "Mehr" })).toBeVisible();
    await shoot(page, `mobile-more-sheet-${viewportName}`);
  });
}
