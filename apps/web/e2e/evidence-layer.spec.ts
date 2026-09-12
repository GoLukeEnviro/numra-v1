import { expect, test, type Page, type Route } from "@playwright/test";

const USER = { id: "user-1", email: "lukas@example.com", role: "USER", is_active: true };
const PERSON = { id: "person-1", user_id: USER.id, person_account_mode: "SELF", birth_first_names: "Lukas", birth_last_name: "Beispiel", birth_date: "1990-03-14", birth_time: null, birth_place: null, preferred_name: null, pronouns: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" };
const RESULT = { sample_size: 18, observation_window_days: 42, confidence_category: "MEDIUM", effect_size: 0.44, baseline_mean: 5.4, bucket_mean: 6.8, statement_text: "An den bislang beobachteten Personal-Day-5-Tagen lag deine gemessene Energie im Mittel höher als deine persönliche Baseline.", evidence_policy_version: 1 };

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

async function mockEvidence(page: Page) {
  const entries: Record<string, unknown>[] = [];
  await page.route("**/v1/auth/me", (route) => json(route, USER));
  await page.route("**/v1/people/person-1", (route) => json(route, PERSON));
  await page.route("**/v1/people/person-1/life-tracking-entries**", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      const created = { ...body, id: "entry-1", person_id: PERSON.id, calculation_id: null, custom_metrics: {}, created_at: "2026-09-12T08:00:00Z", updated_at: "2026-09-12T08:00:00Z" };
      entries.unshift(created);
      await json(route, created, 201);
      return;
    }
    await json(route, entries);
  });
  await page.route("**/v1/people/person-1/pattern-analyses**", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      await json(route, { ...body, id: "analysis-1", person_id: PERSON.id, evidence_policy_version: 1, result: RESULT, created_at: "2026-09-12T08:00:00Z" }, 201);
      return;
    }
    await json(route, []);
  });
  await page.route("**/v1/people/person-1/evidence-results**", (route) => json(route, RESULT));
}

for (const [name, viewport] of Object.entries({ desktop: { width: 1440, height: 900 }, mobile: { width: 390, height: 844 } })) {
  test(`life tracking produces a qualified evidence result on ${name}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await mockEvidence(page);
    await page.goto("/people/person-1/evidence");

    await expect(page.getByRole("heading", { name: "Life Tracking & Evidenz" })).toBeVisible();
    await page.getByLabel("Stimmung").selectOption("8");
    await page.getByLabel("Energie").selectOption("7");
    await page.getByLabel("Notiz (optional)").fill("Klarer Fokus");
    await page.getByRole("button", { name: "Tag speichern" }).click();
    await expect(page.getByText("Klarer Fokus")).toBeVisible();

    await page.getByLabel("Messwert").selectOption("energy");
    await page.getByLabel("Zahl").selectOption("5");
    await page.getByRole("button", { name: "Muster prüfen" }).click();
    await expect(page.getByText(RESULT.statement_text)).toBeVisible();
    await expect(page.getByText("18 Beobachtungen")).toBeVisible();
    await expect(page.getByText("42 Tage Zeitraum")).toBeVisible();
    await expect(page.getByText("Mittlere Sicherheit")).toBeVisible();
  });
}
