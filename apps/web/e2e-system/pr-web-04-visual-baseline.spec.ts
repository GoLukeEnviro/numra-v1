import { test, expect, type Page, type Route } from "@playwright/test";

/**
 * Screenshot generator for the human reality-check on PR-WEB-04 (Relationship
 * Workspace Core). Same pattern as pr-web-03: every API call is mocked with
 * page.route() (no real backend), run under playwright.visual-baseline.config.ts.
 * Every screenshot lands under test-results/pr-web-04/.
 */

const USER = { id: "user-1", email: "lukas@example.com", role: "USER", is_active: true };

function connection(id: string, name: string) {
  return {
    id,
    counterpart_user_id: `counterpart-${id}`,
    counterpart_display_name: name,
    status: "ACTIVE",
    created_at: "2026-08-20T09:00:00Z",
    dissolved_at: null,
  };
}

const CONNECTIONS = [connection("conn-1", "Ada Lovelace"), connection("conn-2", "Grace Hopper")];

const WORKSPACE_ACTIVE = {
  id: "workspace-1",
  connection_id: "conn-1",
  status: "ACTIVE",
  relationship_type: "PARTNER",
  created_at: "2026-08-20T09:00:00Z",
  dissolved_at: null,
};

const WORKSPACE_DISSOLVED = {
  id: "workspace-2",
  connection_id: "conn-2",
  status: "DISSOLVED",
  relationship_type: "FRIENDSHIP",
  created_at: "2026-06-01T09:00:00Z",
  dissolved_at: "2026-08-15T09:00:00Z",
};

function coreNumber(value: string) {
  return { display_value: value };
}

const SELF_MEMBER_FULL = {
  user_id: "user-1",
  display_name: "Lukas Springer",
  self_person: { id: "person-1", display_name: "Lukas Springer" },
  core_numbers: {
    life_path: coreNumber("8"),
    expression: coreNumber("3"),
    soul_urge: coreNumber("5"),
    personality: coreNumber("1"),
    maturity: coreNumber("11"),
    personal_year: coreNumber("4"),
    personal_month: coreNumber("7"),
    personal_day: coreNumber("2"),
  },
};

const COUNTERPART_MEMBER_FULL = {
  user_id: "counterpart-conn-1",
  display_name: "Ada Lovelace",
  self_person: { id: "person-2", display_name: "Ada Lovelace" },
  core_numbers: {
    life_path: coreNumber("1"),
    expression: coreNumber("6"),
    soul_urge: coreNumber("9"),
    personality: coreNumber("2"),
    maturity: coreNumber("7"),
    personal_year: coreNumber("3"),
    personal_month: coreNumber("5"),
    personal_day: coreNumber("6"),
  },
};

const COUNTERPART_MEMBER_NO_CONSENT = {
  user_id: "counterpart-conn-1",
  display_name: "Ada Lovelace",
  self_person: null,
  core_numbers: null,
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
    grant(s, "user-1", "counterpart-conn-1"),
  ),
  granted_to_me: ["CORE_NUMEROLOGY"].map((s) => grant(s, "counterpart-conn-1", "user-1")),
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
  await page.screenshot({ path: `test-results/pr-web-04/${name}.png`, fullPage: true });
}

for (const [viewportName, size] of Object.entries(VIEWPORTS)) {
  test(`workspaces list -- mixed active and dissolved -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuth(page);
    await page.route("**/v1/connections", (route) => fulfillJson(route, 200, CONNECTIONS));
    await page.route("**/v1/workspaces", (route) => fulfillJson(route, 200, [WORKSPACE_ACTIVE, WORKSPACE_DISSOLVED]));
    await page.goto("/workspaces");
    await expect(page.getByText("Aktive Workspaces")).toBeVisible();
    await expect(page.getByText("Aufgelöste Workspaces")).toBeVisible();
    await shoot(page, `workspaces-list-mixed-${viewportName}`);
  });

  test(`workspaces list -- empty -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuth(page);
    await page.route("**/v1/connections", (route) => fulfillJson(route, 200, []));
    await page.route("**/v1/workspaces", (route) => fulfillJson(route, 200, []));
    await page.goto("/workspaces");
    await expect(page.getByText("Noch keine Workspaces")).toBeVisible();
    await shoot(page, `workspaces-list-empty-${viewportName}`);
  });

  test(`workspace hub -- full consent on both sides -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuth(page);
    await page.route("**/v1/connections", (route) => fulfillJson(route, 200, CONNECTIONS));
    await page.route("**/v1/workspaces", (route) =>
      route.request().url().endsWith("/v1/workspaces")
        ? fulfillJson(route, 200, [WORKSPACE_ACTIVE])
        : route.continue(),
    );
    await page.route("**/v1/workspaces/workspace-1", (route) =>
      fulfillJson(route, 200, { workspace: WORKSPACE_ACTIVE, dual_profile: [SELF_MEMBER_FULL, COUNTERPART_MEMBER_FULL] }),
    );
    await page.route("**/v1/workspaces/workspace-1/consent", (route) => fulfillJson(route, 200, CONSENT_DEFAULT));
    await page.goto("/workspaces/workspace-1");
    await expect(page.getByRole("heading", { name: "Ada Lovelace", level: 1 })).toBeVisible();
    await shoot(page, `workspace-hub-full-consent-${viewportName}`);
  });

  test(`workspace hub -- counterpart without consent degrades gracefully -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuth(page);
    await page.route("**/v1/connections", (route) => fulfillJson(route, 200, CONNECTIONS));
    await page.route("**/v1/workspaces", (route) =>
      route.request().url().endsWith("/v1/workspaces")
        ? fulfillJson(route, 200, [WORKSPACE_ACTIVE])
        : route.continue(),
    );
    await page.route("**/v1/workspaces/workspace-1", (route) =>
      fulfillJson(route, 200, {
        workspace: WORKSPACE_ACTIVE,
        dual_profile: [SELF_MEMBER_FULL, COUNTERPART_MEMBER_NO_CONSENT],
      }),
    );
    await page.route("**/v1/workspaces/workspace-1/consent", (route) => fulfillJson(route, 200, CONSENT_DEFAULT));
    await page.goto("/workspaces/workspace-1");
    await expect(page.getByText("hat die Kernzahlen noch nicht freigegeben.")).toBeVisible();
    await shoot(page, `workspace-hub-graceful-empty-${viewportName}`);
  });

  test(`workspace hub -- interactive type selector on an active workspace -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuth(page);
    await page.route("**/v1/connections", (route) => fulfillJson(route, 200, CONNECTIONS));
    const unsetWorkspace = { ...WORKSPACE_ACTIVE, relationship_type: null };
    await page.route("**/v1/workspaces", (route) =>
      route.request().url().endsWith("/v1/workspaces")
        ? fulfillJson(route, 200, [unsetWorkspace])
        : route.continue(),
    );
    await page.route("**/v1/workspaces/workspace-1", (route) =>
      fulfillJson(route, 200, { workspace: unsetWorkspace, dual_profile: [SELF_MEMBER_FULL, COUNTERPART_MEMBER_FULL] }),
    );
    await page.route("**/v1/workspaces/workspace-1/consent", (route) => fulfillJson(route, 200, CONSENT_DEFAULT));
    await page.goto("/workspaces/workspace-1");
    await expect(page.getByRole("combobox")).toBeVisible();
    await shoot(page, `workspace-hub-type-selector-active-${viewportName}`);
  });

  test(`workspace hub -- DISSOLVED type selector is read-only -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuth(page);
    await page.route("**/v1/connections", (route) => fulfillJson(route, 200, CONNECTIONS));
    await page.route("**/v1/workspaces", (route) =>
      route.request().url().endsWith("/v1/workspaces")
        ? fulfillJson(route, 200, [WORKSPACE_DISSOLVED])
        : route.continue(),
    );
    await page.route("**/v1/workspaces/workspace-2", (route) =>
      fulfillJson(route, 200, { workspace: WORKSPACE_DISSOLVED, dual_profile: [SELF_MEMBER_FULL, COUNTERPART_MEMBER_NO_CONSENT] }),
    );
    await page.route("**/v1/workspaces/workspace-2/consent", (route) => fulfillJson(route, 200, CONSENT_DEFAULT));
    await page.goto("/workspaces/workspace-2");
    await expect(page.getByText("Workspace aufgelöst")).toBeVisible();
    await shoot(page, `workspace-hub-dissolved-readonly-${viewportName}`);
  });

  test(`consent page -- with nav tabs -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockAuth(page);
    await page.route("**/v1/workspaces/workspace-1", (route) =>
      fulfillJson(route, 200, { workspace: WORKSPACE_ACTIVE, dual_profile: [SELF_MEMBER_FULL, COUNTERPART_MEMBER_FULL] }),
    );
    await page.route("**/v1/workspaces/workspace-1/consent", (route) => fulfillJson(route, 200, CONSENT_DEFAULT));
    await page.goto("/workspaces/workspace-1/consent");
    await expect(page.getByRole("link", { name: "Übersicht" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Freigaben" })).toBeVisible();
    await shoot(page, `consent-page-with-nav-tabs-${viewportName}`);
  });
}
