import { test, expect, type Page, type Route } from "@playwright/test";

/**
 * Screenshot generator for the human reality-check on PR-WEB-03 (Connections,
 * Invitations, Consent). Same pattern as pr-web-02: every API call is mocked with
 * page.route() (no real backend), run under playwright.visual-baseline.config.ts.
 * Every screenshot lands under test-results/pr-web-03/.
 */

const USER = { id: "user-1", email: "lukas@example.com", role: "USER", is_active: true };

const CONNECTION_ACCEPTED = {
  id: "conn-1",
  user_a_id: "user-1",
  user_b_id: "user-2",
  status: "ACTIVE",
  created_at: "2026-08-20T09:00:00Z",
  dissolved_at: null,
  counterpart_user_id: "user-2",
  counterpart_display_name: "Ada Lovelace",
};

function invitation(state: string, id: string, method = "LINK") {
  return {
    id,
    method,
    invitee_email: method === "EMAIL" ? "friend@example.com" : null,
    state,
    expires_at: "2026-09-20T00:00:00Z",
    created_at: "2026-09-06T00:00:00Z",
  };
}

const INVITE_CREATED_LINK = {
  ...invitation("PENDING", "invite-link"),
  token: "one-time-link-token",
  redeem_url: "https://app.example.com/connections/redeem?token=one-time-link-token",
};
const INVITE_CREATED_CODE = {
  ...invitation("PENDING", "invite-code", "CODE"),
  token: "SHORTCODE1",
  redeem_url: "https://app.example.com/connections/redeem?token=SHORTCODE1",
};
const INVITE_CREATED_EMAIL = {
  ...invitation("PENDING", "invite-email", "EMAIL"),
  token: "email-invite-token",
  redeem_url: "https://app.example.com/connections/redeem?token=email-invite-token",
};

const PREVIEW = { id: "invite-preview", method: "LINK", expires_at: "2026-09-20T00:00:00Z" };

const WORKSPACE_OVERVIEW = {
  workspace: {
    id: "workspace-1",
    connection_id: "conn-1",
    status: "ACTIVE",
    relationship_type: null,
    created_at: "2026-08-20T09:00:00Z",
    dissolved_at: null,
  },
  dual_profile: [
    { user_id: "user-1", display_name: "Lukas Springer", self_person: null, core_numbers: null },
    { user_id: "user-2", display_name: "Ada Lovelace", self_person: null, core_numbers: null },
  ],
};

function grant(scope: string, grantorId: string, granteeId: string) {
  return {
    id: `grant-${scope}-${grantorId}`,
    workspace_id: "workspace-1",
    grantor_user_id: grantorId,
    grantee_user_id: granteeId,
    scope,
    granted_at: "2026-08-20T09:00:00Z",
    revoked_at: null,
    version: 1,
  };
}

const CONSENT_DEFAULT = {
  granted_by_me: ["CORE_NUMEROLOGY", "RELATIONSHIP_INSIGHTS", "CURRENT_TIMING"].map((s) =>
    grant(s, "user-1", "user-2"),
  ),
  granted_to_me: ["CORE_NUMEROLOGY", "RELATIONSHIP_INSIGHTS"].map((s) => grant(s, "user-2", "user-1")),
};

async function fulfillJson(route: Route, status: number, body: unknown) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

async function mockAuth(page: Page) {
  await page.route("**/v1/auth/me", (route) => fulfillJson(route, 200, USER));
}

const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  mobile390: { width: 390, height: 844 },
} as const;

async function shoot(page: Page, name: string) {
  await page.screenshot({ path: `test-results/pr-web-03/${name}.png`, fullPage: true });
}

for (const [viewportName, size] of Object.entries(VIEWPORTS)) {
  test(`connections -- empty state -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuth(page);
    await page.route("**/v1/connections", (route) => fulfillJson(route, 200, []));
    await page.route("**/v1/connections/invitations", (route) => fulfillJson(route, 200, []));
    await page.route("**/v1/workspaces", (route) => fulfillJson(route, 200, []));
    await page.goto("/connections");
    await expect(page.getByText("Noch keine Verbindungen")).toBeVisible();
    await shoot(page, `connections-empty-${viewportName}`);
  });

  test(`connections invite -- method chooser -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuth(page);
    await page.goto("/connections/invite");
    await expect(page.getByText("Einladungsmethode wählen")).toBeVisible();
    await shoot(page, `connections-invite-method-chooser-${viewportName}`);
  });

  test(`connections invite -- created LINK -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuth(page);
    await page.route("**/v1/connections/invitations", (route) =>
      route.request().method() === "POST" ? fulfillJson(route, 201, INVITE_CREATED_LINK) : route.continue(),
    );
    await page.goto("/connections/invite");
    await page.getByRole("button", { name: "Weiter" }).click();
    await expect(page.getByText("Einladung erstellt")).toBeVisible();
    await shoot(page, `connections-invite-created-link-${viewportName}`);
  });

  test(`connections invite -- created CODE -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuth(page);
    await page.route("**/v1/connections/invitations", (route) =>
      route.request().method() === "POST" ? fulfillJson(route, 201, INVITE_CREATED_CODE) : route.continue(),
    );
    await page.goto("/connections/invite");
    await page.getByText("Code", { exact: true }).click();
    await page.getByRole("button", { name: "Weiter" }).click();
    await expect(page.locator('input[value="SHORTCODE1"]')).toBeVisible();
    await shoot(page, `connections-invite-created-code-${viewportName}`);
  });

  test(`connections invite -- created EMAIL -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuth(page);
    await page.route("**/v1/connections/invitations", (route) =>
      route.request().method() === "POST" ? fulfillJson(route, 201, INVITE_CREATED_EMAIL) : route.continue(),
    );
    await page.goto("/connections/invite");
    await page.getByText("E-Mail", { exact: true }).click();
    await page.getByLabel("E-Mail-Adresse").fill("friend@example.com");
    await page.getByRole("button", { name: "Weiter" }).click();
    await expect(page.getByText("Einladung erstellt")).toBeVisible();
    await shoot(page, `connections-invite-created-email-${viewportName}`);
  });

  test(`connections redeem -- preview -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuth(page);
    await page.route("**/v1/connections/invitations/redeem/*", (route) => fulfillJson(route, 200, PREVIEW));
    await page.goto("/connections/redeem?token=abc123");
    await expect(page.getByText("Link")).toBeVisible();
    await shoot(page, `connections-redeem-preview-${viewportName}`);
  });

  test(`connections list -- accepted -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuth(page);
    await page.route("**/v1/connections", (route) => fulfillJson(route, 200, [CONNECTION_ACCEPTED]));
    await page.route("**/v1/connections/invitations", (route) => fulfillJson(route, 200, []));
    await page.route("**/v1/workspaces", (route) => fulfillJson(route, 200, [WORKSPACE_OVERVIEW.workspace]));
    await page.goto("/connections");
    await expect(page.getByText("Ada Lovelace")).toBeVisible();
    await shoot(page, `connections-list-accepted-${viewportName}`);
  });

  test(`connections list -- mixed invitation states -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuth(page);
    await page.route("**/v1/connections", (route) => fulfillJson(route, 200, []));
    await page.route("**/v1/connections/invitations", (route) =>
      fulfillJson(route, 200, [
        invitation("PENDING", "inv-1"),
        invitation("EXPIRED", "inv-2"),
        invitation("REVOKED", "inv-3"),
        invitation("DECLINED", "inv-4"),
      ]),
    );
    await page.route("**/v1/workspaces", (route) => fulfillJson(route, 200, []));
    await page.goto("/connections");
    await expect(page.getByText("Ausstehend")).toBeVisible();
    await expect(page.getByText("Abgelaufen")).toBeVisible();
    await shoot(page, `connections-list-mixed-states-${viewportName}`);
  });

  test(`consent page -- default scopes -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuth(page);
    await page.route("**/v1/workspaces/workspace-1", (route) => fulfillJson(route, 200, WORKSPACE_OVERVIEW));
    await page.route("**/v1/workspaces/workspace-1/consent", (route) => fulfillJson(route, 200, CONSENT_DEFAULT));
    await page.goto("/workspaces/workspace-1/consent");
    await expect(page.getByText("Von mir geteilt")).toBeVisible();
    await shoot(page, `consent-page-default-${viewportName}`);
  });

  test(`consent page -- outgoing vs incoming -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuth(page);
    await page.route("**/v1/workspaces/workspace-1", (route) => fulfillJson(route, 200, WORKSPACE_OVERVIEW));
    await page.route("**/v1/workspaces/workspace-1/consent", (route) => fulfillJson(route, 200, CONSENT_DEFAULT));
    await page.goto("/workspaces/workspace-1/consent");
    await expect(page.getByText("Mit mir geteilt")).toBeVisible();
    await expect(page.getByRole("switch").first()).toBeVisible();
    await shoot(page, `consent-outgoing-vs-incoming-${viewportName}`);
  });
}
