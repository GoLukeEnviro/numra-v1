import { test, expect, type Page, type Route } from "@playwright/test";
import {
  relationshipAnalysisResult,
  shadowDynamicsResult,
} from "../src/fixtures/analysis";

/**
 * Screenshot generator for the human reality-check on PR-WEB-05 (Relationship /
 * Shadow Analysis UI). Same pattern as pr-web-04: every API call is mocked with
 * page.route() (no real backend), run under playwright.visual-baseline.config.ts.
 * Every screenshot lands under test-results/pr-web-05/.
 *
 * Per PR-WEB-05 design decision #2 these are a STRUCTURE smoke only (provenance
 * visible, 7 shadow fields present, no score) — the mock provider's prose is not a
 * human reality-check of the copy.
 */

const USER = { id: "user-1", email: "lukas@example.com", role: "USER", is_active: true };

const WORKSPACE_ACTIVE = {
  id: "workspace-1",
  connection_id: "conn-1",
  status: "ACTIVE",
  relationship_type: "PARTNER",
  created_at: "2026-08-20T09:00:00Z",
  dissolved_at: null,
};

const WORKSPACE_DISSOLVED = {
  ...WORKSPACE_ACTIVE,
  status: "DISSOLVED",
  dissolved_at: "2026-09-01T09:00:00Z",
};

const SELF_MEMBER = {
  user_id: "user-1",
  display_name: "Lukas Springer",
  self_person: { id: "person-1", display_name: "Lukas Springer" },
  core_numbers: null,
};
const COUNTERPART_MEMBER = {
  user_id: "counterpart-conn-1",
  display_name: "Ada Lovelace",
  self_person: null,
  core_numbers: null,
};

function overview(workspace: unknown) {
  return { workspace, dual_profile: [SELF_MEMBER, COUNTERPART_MEMBER] };
}

function analysisRow(over: Record<string, unknown>) {
  return {
    id: "analysis-1",
    workspace_id: "workspace-1",
    job_id: "job-1",
    status: "PENDING",
    relationship_type: "PARTNER",
    result: null,
    calculation_version: "1.0.0",
    knowledge_version: "de-v1",
    prompt_version: "1",
    model_provider: "mock",
    model_name: "mock-1",
    created_at: "2026-09-01T09:00:00Z",
    generated_at: null,
    ...over,
  };
}

function job(over: Record<string, unknown>) {
  return {
    id: "job-1",
    workspace_id: "workspace-1",
    analysis_type: "RELATIONSHIP_INTERPRETATION",
    status: "GENERATING",
    progress: 80,
    error_code: null,
    attempt_count: 1,
    created_at: "2026-09-01T09:00:00Z",
    updated_at: "2026-09-01T09:03:00Z",
    ...over,
  };
}

async function fulfillJson(route: Route, status: number, body: unknown) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  mobile390: { width: 390, height: 844 },
} as const;

async function shoot(page: Page, name: string) {
  await page.screenshot({ path: `test-results/pr-web-05/${name}.png`, fullPage: true });
}

interface SectionMock {
  latestStatus: number;
  latestBody: unknown;
  jobBody?: unknown;
  byIdBody?: unknown;
}

async function setup(
  page: Page,
  size: { width: number; height: number },
  workspace: unknown,
  relationship: SectionMock,
  shadow: SectionMock,
) {
  await page.setViewportSize(size);
  await page.route("**/v1/auth/me", (route) => fulfillJson(route, 200, USER));
  await page.route("**/v1/connections", (route) => fulfillJson(route, 200, []));
  await page.route("**/v1/workspaces", (route) =>
    route.request().url().endsWith("/v1/workspaces")
      ? fulfillJson(route, 200, [WORKSPACE_ACTIVE])
      : route.continue(),
  );
  await page.route("**/v1/workspaces/workspace-1", (route) => fulfillJson(route, 200, overview(workspace)));
  await page.route("**/v1/workspaces/workspace-1/consent", (route) =>
    fulfillJson(route, 200, { granted_by_me: [], granted_to_me: [] }),
  );

  for (const [slug, mock] of [
    ["relationship-analysis", relationship],
    ["shadow-dynamics", shadow],
  ] as const) {
    await page.route(`**/v1/workspaces/workspace-1/${slug}`, (route) =>
      fulfillJson(route, mock.latestStatus, mock.latestBody),
    );
    await page.route(`**/v1/workspaces/workspace-1/${slug}/*`, (route) =>
      fulfillJson(route, 200, mock.byIdBody ?? mock.latestBody),
    );
  }
  await page.route("**/v1/analysis-jobs/*", (route) => {
    const url = route.request().url();
    const body = url.includes("shadow") ? shadow.jobBody : relationship.jobBody;
    return fulfillJson(route, 200, body ?? job({ status: "GENERATING", progress: 80 }));
  });
}

const NO_ANALYSIS: SectionMock = { latestStatus: 404, latestBody: { code: "NOT_FOUND", message: "none" } };
const RUNNING: SectionMock = {
  latestStatus: 200,
  latestBody: analysisRow({ status: "PENDING" }),
  jobBody: job({ status: "GENERATING", progress: 80 }),
};
const RELATIONSHIP_COMPLETE: SectionMock = {
  latestStatus: 200,
  latestBody: analysisRow({
    id: "analysis-rel",
    job_id: "job-rel",
    status: "COMPLETE",
    result: relationshipAnalysisResult,
  }),
};
const SHADOW_COMPLETE: SectionMock = {
  latestStatus: 200,
  latestBody: analysisRow({
    id: "analysis-shadow",
    job_id: "job-shadow",
    status: "COMPLETE",
    result: shadowDynamicsResult,
  }),
};
const FAILED: SectionMock = {
  latestStatus: 200,
  latestBody: analysisRow({ status: "PENDING" }),
  jobBody: job({ status: "FAILED", progress: 40, error_code: "PROVIDER_TIMEOUT", attempt_count: 2 }),
};

for (const [viewportName, size] of Object.entries(VIEWPORTS)) {
  test(`dynamics -- no analysis yet -- ${viewportName}`, async ({ page }) => {
    await setup(page, size, WORKSPACE_ACTIVE, NO_ANALYSIS, NO_ANALYSIS);
    await page.goto("/workspaces/workspace-1/dynamics");
    await expect(page.getByRole("button", { name: "Beziehungsanalyse starten" })).toBeVisible();
    await shoot(page, `dynamics-empty-${viewportName}`);
  });

  test(`dynamics -- job running -- ${viewportName}`, async ({ page }) => {
    await setup(page, size, WORKSPACE_ACTIVE, RUNNING, NO_ANALYSIS);
    await page.goto("/workspaces/workspace-1/dynamics");
    await expect(page.getByText("Die Analyse wird erstellt")).toBeVisible();
    await shoot(page, `dynamics-running-${viewportName}`);
  });

  test(`dynamics -- relationship complete -- ${viewportName}`, async ({ page }) => {
    await setup(page, size, WORKSPACE_ACTIVE, RELATIONSHIP_COMPLETE, NO_ANALYSIS);
    await page.goto("/workspaces/workspace-1/dynamics");
    await expect(page.getByRole("heading", { name: "Kommunikation" })).toBeVisible();
    await shoot(page, `dynamics-relationship-complete-${viewportName}`);
  });

  test(`dynamics -- shadow complete -- ${viewportName}`, async ({ page }) => {
    await setup(page, size, WORKSPACE_ACTIVE, NO_ANALYSIS, SHADOW_COMPLETE);
    await page.goto("/workspaces/workspace-1/dynamics");
    await expect(page.getByRole("heading", { name: "Person A" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Person B" })).toBeVisible();
    await shoot(page, `dynamics-shadow-complete-${viewportName}`);
  });

  test(`dynamics -- failed -- ${viewportName}`, async ({ page }) => {
    await setup(page, size, WORKSPACE_ACTIVE, FAILED, NO_ANALYSIS);
    await page.goto("/workspaces/workspace-1/dynamics");
    await expect(page.getByText("PROVIDER_TIMEOUT")).toBeVisible();
    await shoot(page, `dynamics-failed-${viewportName}`);
  });

  test(`dynamics -- consent not granted -- ${viewportName}`, async ({ page }) => {
    const gate: SectionMock = {
      latestStatus: 403,
      latestBody: { code: "CONSENT_NOT_GRANTED", message: "both sides must consent" },
    };
    await setup(page, size, WORKSPACE_ACTIVE, gate, gate);
    await page.goto("/workspaces/workspace-1/dynamics");
    await expect(page.getByText("Beidseitige Freigabe nötig").first()).toBeVisible();
    await shoot(page, `dynamics-consent-not-granted-${viewportName}`);
  });

  test(`dynamics -- relationship type not set -- ${viewportName}`, async ({ page }) => {
    const gate: SectionMock = {
      latestStatus: 409,
      latestBody: { code: "RELATIONSHIP_TYPE_NOT_SET", message: "set a type first" },
    };
    await setup(page, size, WORKSPACE_ACTIVE, gate, NO_ANALYSIS);
    await page.goto("/workspaces/workspace-1/dynamics");
    await expect(page.getByText("Beziehungstyp fehlt")).toBeVisible();
    await shoot(page, `dynamics-relationship-type-not-set-${viewportName}`);
  });

  test(`dynamics -- workspace dissolved -- ${viewportName}`, async ({ page }) => {
    await setup(page, size, WORKSPACE_DISSOLVED, NO_ANALYSIS, NO_ANALYSIS);
    await page.goto("/workspaces/workspace-1/dynamics");
    await expect(page.getByText("Workspace aufgelöst")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Beziehungsanalyse" })).toHaveCount(0);
    await shoot(page, `dynamics-workspace-dissolved-${viewportName}`);
  });
}
