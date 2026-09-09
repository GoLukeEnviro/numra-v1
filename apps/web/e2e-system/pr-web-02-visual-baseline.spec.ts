import { test, expect, type Page, type Route } from "@playwright/test";

/**
 * Screenshot generator for the human reality-check on PR-WEB-02 (Personal
 * Workspace: Notes, Reflections, Tasks). Same pattern as pr-web-00/01: every API
 * call is mocked with page.route() (no real backend), run under
 * playwright.visual-baseline.config.ts. Every screenshot lands under
 * test-results/pr-web-02/.
 */

const USER = { id: "user-1", email: "lukas@example.com", role: "USER", is_active: true };
const PERSON_A = {
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
  person_account_mode: "SELF",
  created_at: "2026-08-19T09:00:00Z",
  updated_at: "2026-08-19T09:00:00Z",
};
const PERSON_B = {
  ...PERSON_A,
  id: "22222222-2222-2222-2222-222222222222",
  birth_first_names: "Mira",
  birth_last_name: "Springer",
  person_account_mode: "MANAGED_MINOR",
};
const PEOPLE = [PERSON_A, PERSON_B];

const EMPTY_OVERVIEW = {
  person: PERSON_A,
  latest_calculation: null,
  reports: { total: 0, latest: null },
  private_reflections: { total: 0, latest: null },
  private_notes: { total: 0 },
  personal_tasks: { total: 0, active: 0 },
};

const FILLED_OVERVIEW = {
  person: PERSON_A,
  latest_calculation: {
    id: "calc-1",
    person_id: PERSON_A.id,
    as_of_date: "2026-09-01",
    calculation_version: "1",
    schema_version: "1",
    deterministic_hash: "abcdef123456",
    created_at: "2026-09-01T09:00:00Z",
  },
  reports: {
    total: 2,
    latest: {
      id: "report-1",
      calculation_id: "calc-1",
      person: { id: PERSON_A.id, display_name: "Lukas Springer" },
      report_type: "FULL",
      status: "COMPLETE",
      word_count: 4200,
      created_at: "2026-09-01T10:00:00Z",
      generated_at: "2026-09-01T10:05:00Z",
    },
  },
  private_reflections: {
    total: 1,
    latest: { id: "reflection-1", person_id: PERSON_A.id, entry_date: "2026-09-01" },
  },
  private_notes: { total: 2 },
  personal_tasks: { total: 3, active: 2 },
};

const NOTES = [
  {
    id: "note-1",
    person_id: PERSON_A.id,
    title: "First impression",
    content: "Very grounded, practical energy from the first conversation.",
    created_at: "2026-08-20T09:00:00Z",
    updated_at: "2026-08-21T09:00:00Z",
  },
];

const REFLECTIONS = [
  {
    id: "reflection-1",
    person_id: PERSON_A.id,
    entry_date: "2026-09-01",
    content: "A quiet, reflective day -- good time to plan the next quarter.",
    created_at: "2026-09-01T09:00:00Z",
    updated_at: "2026-09-01T09:00:00Z",
  },
];

const TASKS = [
  {
    id: "task-1",
    person_id: PERSON_A.id,
    title: "Call the accountant",
    description: null,
    due_date: null,
    status: "ACTIVE",
    completed_at: null,
    created_at: "2026-08-20T09:00:00Z",
    updated_at: "2026-08-20T09:00:00Z",
  },
  {
    id: "task-2",
    person_id: PERSON_A.id,
    title: "Book the flight",
    description: "Return ticket for the December visit.",
    due_date: "2026-09-15",
    status: "ACTIVE",
    completed_at: null,
    created_at: "2026-08-21T09:00:00Z",
    updated_at: "2026-08-21T09:00:00Z",
  },
];

const TIMING = {
  as_of_date: "2026-09-09",
  universal_year: { display_value: "9" },
  personal_year: { display_value: "3" },
  personal_month: { display_value: "6" },
  personal_day: { display_value: "1" },
};

const DAILY_BRIEF = {
  sections: [
    {
      metric_id: "personal_day",
      display_name_de: "Persönlicher Tag",
      display_value: "1",
      text_de: "Ein Tag für einen frischen Anfang.",
    },
  ],
};

async function fulfillJson(route: Route, status: number, body: unknown) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

async function mockBaseline(page: Page, people: unknown[] = PEOPLE) {
  await page.route("**/v1/auth/me", (route) => fulfillJson(route, 200, USER));
  await page.route("**/v1/people", (route) => fulfillJson(route, 200, people));
}

async function mockWorkspace(page: Page, overview: unknown, notes: unknown[], reflections: unknown[], tasks: unknown[]) {
  await page.route("**/v1/me/workspace**", (route) => fulfillJson(route, 200, overview));
  await page.route(`**/v1/people/${PERSON_A.id}/private-notes**`, (route) =>
    route.request().method() === "POST" ? fulfillJson(route, 201, notes[0] ?? NOTES[0]) : fulfillJson(route, 200, notes),
  );
  await page.route(`**/v1/people/${PERSON_A.id}/private-reflections**`, (route) =>
    route.request().method() === "POST"
      ? fulfillJson(route, 201, reflections[0] ?? REFLECTIONS[0])
      : fulfillJson(route, 200, reflections),
  );
  await page.route(`**/v1/people/${PERSON_A.id}/personal-tasks**`, (route) =>
    route.request().method() === "POST" ? fulfillJson(route, 201, tasks[0] ?? TASKS[0]) : fulfillJson(route, 200, tasks),
  );
}

const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  mobile390: { width: 390, height: 844 },
} as const;

async function shoot(page: Page, name: string) {
  await page.screenshot({ path: `test-results/pr-web-02/${name}.png`, fullPage: true });
}

for (const [viewportName, size] of Object.entries(VIEWPORTS)) {
  test(`workspace hub -- empty panels -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockBaseline(page);
    await mockWorkspace(page, EMPTY_OVERVIEW, [], [], []);
    await page.goto(`/people/${PERSON_A.id}/workspace`);
    await expect(page.getByRole("heading", { name: "Lukas Springer" })).toBeVisible();
    await expect(page.getByText("Noch keine Aufgaben")).toBeVisible();
    await expect(page.getByText("Noch keine Notizen")).toBeVisible();
    await expect(page.getByText("Noch keine Reflexionen")).toBeVisible();
    await shoot(page, `workspace-hub-empty-${viewportName}`);
  });

  test(`workspace hub -- filled clusters -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockBaseline(page);
    await mockWorkspace(page, FILLED_OVERVIEW, NOTES, REFLECTIONS, TASKS);
    await page.goto(`/people/${PERSON_A.id}/workspace`);
    await expect(page.getByRole("link", { name: /Profilanalyse öffnen/ })).toBeVisible();
    await expect(page.getByText("Call the accountant")).toBeVisible();
    await expect(page.getByText("First impression")).toBeVisible();
    await shoot(page, `workspace-hub-filled-${viewportName}`);
  });

  test(`workspace hub -- create-note form open -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockBaseline(page);
    await mockWorkspace(page, EMPTY_OVERVIEW, [], [], []);
    await page.goto(`/people/${PERSON_A.id}/workspace`);
    await page.getByRole("button", { name: /Erste Notiz erstellen/ }).click();
    await expect(page.getByLabel("Inhalt")).toBeVisible();
    await shoot(page, `workspace-hub-note-create-open-${viewportName}`);
  });

  test(`workspace hub -- task marked completed -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockBaseline(page);
    // Stateful mock: the PATCH flips task-1's status, and the subsequent list
    // reload must reflect that -- otherwise the checkbox would bounce back
    // unchecked once the panel refetches.
    let task1Status: "ACTIVE" | "COMPLETED" = "ACTIVE";
    await page.route("**/v1/me/workspace**", (route) => fulfillJson(route, 200, FILLED_OVERVIEW));
    await page.route(`**/v1/people/${PERSON_A.id}/private-notes**`, (route) => fulfillJson(route, 200, NOTES));
    await page.route(`**/v1/people/${PERSON_A.id}/private-reflections**`, (route) =>
      fulfillJson(route, 200, REFLECTIONS),
    );
    await page.route(`**/v1/people/${PERSON_A.id}/personal-tasks**`, (route) =>
      fulfillJson(
        route,
        200,
        TASKS.map((task) => (task.id === "task-1" ? { ...task, status: task1Status } : task)),
      ),
    );
    await page.route("**/v1/personal-tasks/task-1", (route) => {
      task1Status = "COMPLETED";
      return fulfillJson(route, 200, {
        ...TASKS[0],
        status: "COMPLETED",
        completed_at: "2026-09-09T09:00:00Z",
      });
    });
    await page.goto(`/people/${PERSON_A.id}/workspace`);
    const checkbox = page.getByLabel(/Erledigt markieren: Call the accountant/);
    await checkbox.click();
    await expect(checkbox).toBeChecked();
    await shoot(page, `workspace-hub-task-completed-${viewportName}`);
  });

  test(`/today with person_id query param -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockBaseline(page);
    await page.route(`**/v1/people/${PERSON_B.id}/timing**`, (route) => fulfillJson(route, 200, TIMING));
    await page.route(`**/v1/people/${PERSON_B.id}/daily-brief**`, (route) => fulfillJson(route, 200, DAILY_BRIEF));
    await page.goto(`/today?person_id=${PERSON_B.id}`);
    await expect(page.getByRole("option", { name: /Mira Springer/ })).toHaveAttribute("value", PERSON_B.id);
    await expect(page.locator("#today-person")).toHaveValue(PERSON_B.id);
    await shoot(page, `today-person-query-param-${viewportName}`);
  });

  test(`workspace switcher -- SELF vs managed profile -- ${viewportName}`, async ({ page }) => {
    await page.setViewportSize(size);
    await mockBaseline(page);
    await mockWorkspace(page, EMPTY_OVERVIEW, [], [], []);
    await page.goto(`/people/${PERSON_A.id}/workspace`);
    const switcher = page.getByRole("combobox", { name: "Workspace wechseln" });
    await expect(switcher).toBeVisible();
    await expect(page.getByText("Eigenes Profil", { exact: true })).toBeVisible();
    const options = await switcher.locator("option").allTextContents();
    expect(options.some((o) => o.includes("Eigenes Profil"))).toBe(true);
    expect(options.some((o) => o.includes("Verwaltetes Profil"))).toBe(true);
    await shoot(page, `workspace-switcher-self-vs-managed-${viewportName}`);
  });
}
