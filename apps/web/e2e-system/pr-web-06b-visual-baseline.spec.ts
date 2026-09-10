import { expect, test, type Page, type Route } from "@playwright/test";

const USER = { id: "user-1", email: "lukas@example.com", role: "USER", is_active: true };
const ACTIVE = { id: "workspace-1", connection_id: "conn-1", status: "ACTIVE", relationship_type: "PARTNER", created_at: "2026-08-20T09:00:00Z", dissolved_at: null };
const DISSOLVED = { ...ACTIVE, status: "DISSOLVED", dissolved_at: "2026-09-09T09:00:00Z" };
const MEMBERS = [
  { user_id: "user-1", display_name: "Lukas Springer", self_person: null, core_numbers: null },
  { user_id: "user-2", display_name: "Ada Lovelace", self_person: null, core_numbers: null },
];
const DIMENSION = { dimension_id: "dimension-1", semantic_key: "closeness", label: "Nähe und Verbundenheit", description: "Wie nah und verbunden fühlst du dich in eurer Beziehung?", scale_min: 1, scale_max: 10, sort_order: 0 };
const TEMPLATE_DIMENSION = { id: "dimension-1", semantic_key: "closeness", label: DIMENSION.label, description: DIMENSION.description, scale_min: 1, scale_max: 10, sort_order: 0, active: true, retired_at: null, dimension_class: null };
const TEMPLATE = { id: "template-1", version: 1, active: true, dimensions: [TEMPLATE_DIMENSION] };
const SUMMARY = { id: "round-1", checkin_template_version: 1, status: "ANALYZED", cycle_started_at: "2026-09-10T09:00:00Z" };

function round(overrides: Record<string, unknown> = {}) {
  return { id: "round-1", workspace_id: "workspace-1", checkin_template_version: 1, status: "AWAITING_SUBMISSIONS", cycle_started_at: "2026-09-10T09:00:00Z", snapshot_origin: "ROUND_START", snapshot_recorded: true, dimensions: [DIMENSION], my_responses: [], partner_submitted: false, analysis: null, ...overrides };
}

const RESULT = round({
  status: "ANALYZED",
  my_responses: [{ dimension_id: "dimension-1", semantic_key: "closeness", value: 7, submitted_at: "2026-09-10T09:05:00Z" }],
  partner_submitted: true,
  analysis: { computed_at: "2026-09-10T09:06:00Z", result: { closeness: { absolute_gap: 2, direction: "CONVERGING", rolling_trend: 2.7, sample_size: 4, historical_delta: -1.5, sufficient_evidence: true } } },
});

async function json(route: Route, status: number, body: unknown) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

type Scenario = { workspace?: typeof ACTIVE | typeof DISSOLVED; current: unknown; history?: readonly unknown[]; template?: unknown };

async function setup(page: Page, size: { width: number; height: number }, scenario: Scenario) {
  await page.setViewportSize(size);
  await page.route("**/v1/auth/me", (route) => json(route, 200, USER));
  await page.route("**/v1/connections", (route) => json(route, 200, []));
  await page.route("**/v1/workspaces", (route) => route.request().url().endsWith("/v1/workspaces") ? json(route, 200, [ACTIVE]) : route.continue());
  await page.route("**/v1/workspaces/workspace-1", (route) => json(route, 200, { workspace: scenario.workspace ?? ACTIVE, dual_profile: MEMBERS }));
  await page.route("**/v1/workspaces/workspace-1/checkins/current", (route) => json(route, 200, scenario.current));
  await page.route("**/v1/workspaces/workspace-1/checkins?*", (route) => json(route, 200, scenario.history ?? []));
  await page.route("**/v1/workspaces/workspace-1/checkin-template", (route) => scenario.template === null ? json(route, 404, { code: "NOT_FOUND", message: "none" }) : json(route, 200, scenario.template ?? TEMPLATE));
}

const VIEWPORTS = { desktop: { width: 1440, height: 900 }, mobile390: { width: 390, height: 844 } } as const;

for (const [name, size] of Object.entries(VIEWPORTS)) {
  for (const [state, scenario, expected] of [
    ["empty", { current: null }, "Bereit für eine neue Runde"],
    ["form-config-locked", { current: round() }, "Deine Sicht heute"],
    ["waiting", { current: round({ my_responses: [{ dimension_id: "dimension-1", semantic_key: "closeness", value: 7, submitted_at: "2026-09-10T09:05:00Z" }] }) }, "Deine Seite ist abgegeben"],
    ["result", { current: RESULT, history: [SUMMARY] }, "Auswertung dieser Runde"],
    ["result-building", { current: round({ ...RESULT, analysis: { computed_at: "2026-09-10T09:06:00Z", result: { closeness: { absolute_gap: 2, direction: "NO_PRIOR_DATA", rolling_trend: 2, sample_size: 1, historical_delta: null, sufficient_evidence: false } } } }), history: [SUMMARY] }, "Noch nicht verfügbar"],
    ["dissolved-empty", { workspace: DISSOLVED, current: null, history: [], template: null }, "Historische Ansicht"],
  ] as const) {
    test(`check-ins -- ${state} -- ${name}`, async ({ page }) => {
      await setup(page, size, scenario);
      await page.goto("/workspaces/workspace-1/checkins");
      await expect(page.getByText(expected, { exact: true }).first()).toBeVisible();
      await page.screenshot({ path: `test-results/pr-web-06b/checkins-${state}-${name}.png`, fullPage: true });
    });
  }
}
