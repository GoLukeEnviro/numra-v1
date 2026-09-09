import { test, expect, type Page, type Route } from "@playwright/test";

/**
 * Screenshot generator for the human reality-check on PR-WEB-00B (AVENYTH
 * frontend/PWA brand closure). Same shape as pr-web-00-visual-baseline.spec.ts
 * (mocks every API call with page.route(), no real backend needed) and runs
 * under the same playwright.visual-baseline.config.ts. Every screenshot lands
 * under test-results/pr-web-00b/.
 *
 * Purpose here is narrower than PR-WEB-00's spec: prove the brand migration
 * actually reached the rendered DOM (document.title contains "AVENYTH") across
 * the touchpoints a person sees before ever creating a profile, plus the
 * already-authenticated shell -- not a full re-run of every app state.
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
const PUBLIC_CONFIG = {
  self_signup_enabled: true,
  app_name: "AVENYTH",
  supported_ui_locales: ["de", "en"],
};

async function fulfillJson(route: Route, status: number, body: unknown) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

async function mockAnonymousApi(page: Page) {
  await page.route("**/v1/auth/me", (route) =>
    fulfillJson(route, 401, { code: "UNAUTHENTICATED", message: "Not authenticated." }),
  );
  await page.route("**/v1/public/config", (route) => fulfillJson(route, 200, PUBLIC_CONFIG));
}

async function mockAuthenticatedApi(page: Page) {
  await page.route("**/v1/auth/me", (route) => fulfillJson(route, 200, USER));
  await page.route("**/v1/people", (route) => fulfillJson(route, 200, [PERSON]));
  await page.route("**/v1/public/config", (route) => fulfillJson(route, 200, PUBLIC_CONFIG));
}

const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  tablet: { width: 768, height: 1024 },
  mobile390: { width: 390, height: 844 },
  mobile430: { width: 430, height: 932 },
} as const;

async function shoot(page: Page, name: string) {
  await page.screenshot({ path: `test-results/pr-web-00b/${name}.png`, fullPage: true });
}

for (const [viewportName, size] of Object.entries(VIEWPORTS)) {
  test(`(landing) public front door -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAnonymousApi(page);
    await page.goto("/");
    expect(await page.title()).toContain("AVENYTH");
    await shoot(page, `landing-${viewportName}`);
  });

  test(`(login) sign-in card -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAnonymousApi(page);
    await page.goto("/login");
    expect(await page.title()).toContain("AVENYTH");
    await shoot(page, `login-${viewportName}`);
  });

  test(`(dashboard) authenticated shell with sidebar/logo -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuthenticatedApi(page);
    await page.goto("/dashboard");
    expect(await page.title()).toContain("AVENYTH");
    await shoot(page, `dashboard-${viewportName}`);
  });

  test(`(connections) -- ${viewportName}`, async ({ page }) => {
    // PR-WEB-03 replaced this route's ComingSoonState placeholder with the real
    // Connections list -- see pr-web-03-visual-baseline.spec.ts for its full coverage.
    await page.setViewportSize(size);
    await mockAuthenticatedApi(page);
    await page.route("**/v1/connections", (route) => fulfillJson(route, 200, []));
    await page.route("**/v1/connections/invitations", (route) => fulfillJson(route, 200, []));
    await page.route("**/v1/workspaces", (route) => fulfillJson(route, 200, []));
    await page.goto("/connections");
    await expect(page.getByRole("heading", { name: "Verbindungen", level: 1 })).toBeVisible();
    expect(await page.title()).toContain("AVENYTH");
    await shoot(page, `connections-${viewportName}`);
  });

  test(`(workspaces) empty -- ${viewportName}`, async ({ page }) => {
    // PR-WEB-04 replaced this route's ComingSoonState placeholder with the real
    // Workspaces list -- see pr-web-04-visual-baseline.spec.ts for its full coverage.
    await page.setViewportSize(size);
    await mockAuthenticatedApi(page);
    await page.route("**/v1/connections", (route) => fulfillJson(route, 200, []));
    await page.route("**/v1/workspaces", (route) => fulfillJson(route, 200, []));
    await page.goto("/workspaces");
    await expect(page.getByText("Noch keine Workspaces")).toBeVisible();
    expect(await page.title()).toContain("AVENYTH");
    await shoot(page, `workspaces-placeholder-${viewportName}`);
  });

  test(`(onboarding) welcome step -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuthenticatedApi(page);
    await page.route("**/v1/people", (route) => fulfillJson(route, 200, []));
    await page.goto("/onboarding");
    await expect(page.getByText("Willkommen bei AVENYTH")).toBeVisible();
    expect(await page.title()).toContain("AVENYTH");
    await shoot(page, `onboarding-welcome-${viewportName}`);
  });
}

for (const viewportName of ["mobile390", "mobile430"] as const) {
  test(`(mobile-nav) bottom nav + "More" sheet open -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(VIEWPORTS[viewportName]);
    await mockAuthenticatedApi(page);
    await page.goto("/dashboard");
    await page.getByRole("button", { name: /Mehr/ }).click();
    await expect(page.getByRole("dialog", { name: "Mehr" })).toBeVisible();
    expect(await page.title()).toContain("AVENYTH");
    await shoot(page, `mobile-more-sheet-${viewportName}`);
  });
}
