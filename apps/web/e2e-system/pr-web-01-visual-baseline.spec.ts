import { test, expect, type Page, type Route } from "@playwright/test";

/**
 * Screenshot generator for the human reality-check on PR-WEB-01 (Auth-Erweiterungen
 * fuer E-Mail-Verifizierung/Passwort-Reset + Entitlements-Anzeige). Same pattern as
 * pr-web-00-visual-baseline.spec.ts: every API call is mocked with page.route() (no
 * real backend), run under playwright.visual-baseline.config.ts. Every screenshot
 * lands under test-results/pr-web-01/.
 */

const VERIFIED_USER: {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  email_verified_at: string | null;
} = {
  id: "user-1",
  email: "lukas@example.com",
  role: "USER",
  is_active: true,
  email_verified_at: "2026-01-01T00:00:00Z",
};
const UNVERIFIED_USER = { ...VERIFIED_USER, email_verified_at: null };
const PEOPLE: unknown[] = [];
const SESSIONS = [
  {
    id: "s1",
    created_at: "2026-09-01T09:00:00Z",
    expires_at: "2026-09-08T09:00:00Z",
    is_current: true,
  },
];
const SYSTEM_INFO = {
  environment: "production",
  app_timezone: "Europe/Berlin",
  session_ttl_hours: 168,
  self_signup_enabled: true,
  llm_provider: "ollama",
  pdf_export_enabled: true,
};
const ENTITLEMENTS = {
  advanced_relationship_analysis: true,
  connections: true,
  life_tracking: false,
  max_connections: 5,
  max_workspaces: null,
  personal_workspace: true,
  premium_reports: false,
  relationship_checkins: true,
  relationship_copilot: false,
  relationship_workspaces: true,
};

async function fulfillJson(route: Route, status: number, body: unknown) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

async function fulfillEmpty(route: Route, status: number) {
  await route.fulfill({ status });
}

async function mockAuthenticatedApi(page: Page, user: typeof VERIFIED_USER) {
  await page.route("**/v1/auth/me", (route) => fulfillJson(route, 200, user));
  await page.route("**/v1/people", (route) => fulfillJson(route, 200, PEOPLE));
  await page.route("**/v1/auth/sessions", (route) => fulfillJson(route, 200, SESSIONS));
  await page.route("**/v1/system-info", (route) => fulfillJson(route, 200, SYSTEM_INFO));
  await page.route("**/v1/me/entitlements", (route) => fulfillJson(route, 200, ENTITLEMENTS));
}

const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  mobile390: { width: 390, height: 844 },
} as const;

async function shoot(page: Page, name: string) {
  await page.screenshot({ path: `test-results/pr-web-01/${name}.png`, fullPage: true });
}

for (const [viewportName, size] of Object.entries(VIEWPORTS)) {
  test(`/forgot-password idle -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await page.goto("/forgot-password");
    await expect(page.getByLabel("E-Mail")).toBeVisible();
    await shoot(page, `forgot-password-idle-${viewportName}`);
  });

  test(`/forgot-password submitted -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await page.route("**/v1/auth/forgot-password", (route) => fulfillEmpty(route, 202));
    await page.goto("/forgot-password");
    await page.getByLabel("E-Mail").fill("someone@example.com");
    await page.getByRole("button", { name: "Link anfordern" }).click();
    await expect(page.getByText("Falls ein Konto mit dieser Adresse existiert")).toBeVisible();
    await shoot(page, `forgot-password-submitted-${viewportName}`);
  });

  test(`/reset-password form -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await page.goto("/reset-password?token=demo-token");
    await expect(page.getByLabel("Neues Passwort", { exact: true })).toBeVisible();
    await shoot(page, `reset-password-form-${viewportName}`);
  });

  test(`/reset-password success -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await page.route("**/v1/auth/reset-password", (route) => fulfillEmpty(route, 204));
    await page.goto("/reset-password?token=demo-token");
    await page.getByLabel("Neues Passwort", { exact: true }).fill("a-strong-password");
    await page.getByLabel("Neues Passwort bestätigen").fill("a-strong-password");
    await page.getByRole("button", { name: "Passwort festlegen" }).click();
    await expect(page.getByText("Passwort wurde geändert")).toBeVisible();
    await shoot(page, `reset-password-success-${viewportName}`);
  });

  test(`/reset-password token-invalid -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await page.route("**/v1/auth/reset-password", (route) =>
      fulfillJson(route, 400, { code: "INVALID_OR_EXPIRED_TOKEN", message: "invalid token" }),
    );
    await page.goto("/reset-password?token=demo-token");
    await page.getByLabel("Neues Passwort", { exact: true }).fill("a-strong-password");
    await page.getByLabel("Neues Passwort bestätigen").fill("a-strong-password");
    await page.getByRole("button", { name: "Passwort festlegen" }).click();
    await expect(page.getByText("Link nicht mehr gültig")).toBeVisible();
    await shoot(page, `reset-password-invalid-${viewportName}`);
  });

  test(`/reset-password missing-token -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await page.goto("/reset-password");
    await expect(page.getByText("Link unvollständig")).toBeVisible();
    await shoot(page, `reset-password-missing-token-${viewportName}`);
  });

  test(`/verify-email verifying -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    // Deliberately never resolves within the test's lifetime -- captures the
    // in-flight loading state before the mocked call would settle.
    await page.route("**/v1/auth/verify-email", () => new Promise(() => {}));
    await page.goto("/verify-email?token=demo-token");
    await expect(page.getByText("E-Mail wird bestätigt")).toBeVisible();
    await shoot(page, `verify-email-verifying-${viewportName}`);
  });

  test(`/verify-email success -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await page.route("**/v1/auth/verify-email", (route) => fulfillEmpty(route, 204));
    await page.goto("/verify-email?token=demo-token");
    await expect(page.getByText("E-Mail bestätigt")).toBeVisible();
    await shoot(page, `verify-email-success-${viewportName}`);
  });

  test(`/verify-email token-invalid -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await page.route("**/v1/auth/verify-email", (route) =>
      fulfillJson(route, 400, { code: "INVALID_OR_EXPIRED_TOKEN", message: "invalid token" }),
    );
    await page.goto("/verify-email?token=demo-token");
    await expect(page.getByText("Link nicht mehr gültig")).toBeVisible();
    await shoot(page, `verify-email-invalid-${viewportName}`);
  });

  test(`/login with forgot-password link visible -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await page.goto("/login");
    await expect(page.getByRole("link", { name: "Passwort vergessen?" })).toBeVisible();
    await shoot(page, `login-forgot-password-link-${viewportName}`);
  });

  test(`/settings with entitlements card + unverified status -- ${viewportName}`, async ({
    page,
  }) => {
    await page.setViewportSize(size);
    await mockAuthenticatedApi(page, UNVERIFIED_USER);
    await page.goto("/settings");
    await expect(page.getByText("E-Mail nicht bestätigt")).toBeVisible();
    await expect(page.getByText("Berechtigungen")).toBeVisible();
    await shoot(page, `settings-unverified-${viewportName}`);
  });

  test(`/settings with entitlements card + verified status -- ${viewportName}`, async ({
    page,
  }) => {
    await page.setViewportSize(size);
    await mockAuthenticatedApi(page, VERIFIED_USER);
    await page.goto("/settings");
    await expect(page.getByText("E-Mail bestätigt")).toBeVisible();
    await expect(page.getByText("Berechtigungen")).toBeVisible();
    await shoot(page, `settings-verified-${viewportName}`);
  });

  test(`EmailVerificationBanner visible on dashboard -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuthenticatedApi(page, UNVERIFIED_USER);
    await page.goto("/dashboard");
    await expect(
      page.getByText("Bitte bestätige deine E-Mail-Adresse, um dein Konto abzusichern."),
    ).toBeVisible();
    await shoot(page, `dashboard-email-verification-banner-${viewportName}`);
  });
}
