import { test, expect, type Page, type Route } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * There is no live backend in this sandbox (apps/api is a real FastAPI +
 * Postgres service that isn't running here), so every API call this journey
 * makes is intercepted with page.route() and answered with fixture data
 * shaped exactly like the real contract in openapi/numra-v1.json. The
 * canonical_profile fixture is the actual golden reference
 * (fixtures/canonical/lukas-springer.v1.json, canon-spec.md §36), read from
 * disk rather than duplicated by hand so this test can't drift from it.
 */

const FIXTURE_PATH = path.resolve(
  dirname,
  "../../../fixtures/canonical/lukas-springer.v1.json",
);
const canonicalProfile = JSON.parse(fs.readFileSync(FIXTURE_PATH, "utf-8"));

const USER = { id: "user-1", email: "lukas@example.com" };
const PERSON_ID = "11111111-1111-1111-1111-111111111111";
const CALCULATION_ID = "22222222-2222-2222-2222-222222222222";

const personOut = {
  id: PERSON_ID,
  birth_first_names: "Lukas",
  birth_middle_names: null,
  birth_last_name: "Springer",
  birth_date: "1986-07-18",
  birth_time: { value: "06:00:00", precision: "exact" },
  birth_place: { display_name: "Meerbusch", country_code: "DE" },
  current_first_names: null,
  current_middle_names: null,
  current_last_name: null,
  preferred_name: null,
  created_at: "2026-08-19T09:00:00Z",
  updated_at: "2026-08-19T09:00:00Z",
};

const calculationOut = {
  id: CALCULATION_ID,
  person_id: PERSON_ID,
  calculation_version: "1.0.0",
  schema_version: "1.0.0",
  as_of_date: "2026-08-19",
  deterministic_hash: "869f161a080f19fdb8ffc70eeb06466982fc6c35b3d3e9f4371dfef4149d1936",
  canonical_profile: canonicalProfile,
  created_at: "2026-08-19T09:00:05Z",
};

async function fulfillJson(route: Route, status: number, body: unknown) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function mockApi(page: Page) {
  await page.route("**/v1/auth/me", (route) =>
    fulfillJson(route, 401, { code: "UNAUTHENTICATED", message: "Not authenticated." }),
  );
  await page.route("**/v1/auth/login", (route) => fulfillJson(route, 200, USER));
  await page.route("**/v1/people", (route) => {
    if (route.request().method() === "POST") {
      return fulfillJson(route, 201, personOut);
    }
    return fulfillJson(route, 200, [personOut]);
  });
  await page.route(`**/v1/people/${PERSON_ID}/calculations`, (route) =>
    fulfillJson(route, 201, calculationOut),
  );
  await page.route(`**/v1/calculations/${CALCULATION_ID}`, (route) =>
    fulfillJson(route, 200, calculationOut),
  );
}

test("golden journey: log in, create a profile, see core numbers, inspect the trace", async ({
  page,
}) => {
  await mockApi(page);

  // 1. Log in
  await page.goto("/login");
  await page.getByLabel("Email").fill(USER.email);
  await page.getByLabel("Password").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  // 2. Create a person
  await page.getByRole("link", { name: "New profile" }).first().click();
  await expect(page).toHaveURL(/\/people\/new$/);

  await page.getByLabel("First name(s) *").fill("Lukas");
  await page.getByLabel("Last name *").fill("Springer");
  await page.getByLabel("Birth date *").fill("1986-07-18");
  await page.getByLabel("Birth time", { exact: true }).fill("06:00");
  await page.getByLabel("Time precision").selectOption("exact");
  await page.getByLabel("Birth place").fill("Meerbusch");
  await page.getByLabel("Country code").fill("DE");

  await page.getByRole("button", { name: /Create profile/i }).click();

  // 3. Land on the analysis page for the new calculation, Core Numbers visible
  await expect(page).toHaveURL(new RegExp(`/analysis/${CALCULATION_ID}$`));
  await expect(page.getByRole("heading", { name: "Lukas Springer" })).toBeVisible();

  await expect(page.getByText("22/4", { exact: true }).first()).toBeVisible(); // Life Path
  await expect(page.getByText("62/8", { exact: true }).first()).toBeVisible(); // Expression
  await expect(page.getByText("18/9", { exact: true }).first()).toBeVisible(); // Soul Urge
  await expect(page.getByText("44/8", { exact: true }).first()).toBeVisible(); // Personality

  // Life Path is a Master Number — the badge must say so.
  await expect(page.getByText(/Master Number 22/i).first()).toBeVisible();

  // 4. Open the Calculation Inspector and confirm the trace is shown
  await page.getByRole("tab", { name: "Calculation Inspector" }).click();
  await expect(page.getByRole("tabpanel")).toBeVisible();

  // The canonical Life Path trace (default-selected metric), per canon-spec.md's
  // worked example: day/month/year segments, the segmented sum, and the reduce.
  await expect(page.getByText("Day: 18 → 9")).toBeVisible();
  await expect(page.getByText("Month: 07 → 7")).toBeVisible();
  await expect(page.getByText("Year: 1986 → 24 → 6")).toBeVisible();
  await expect(page.getByText("9 + 7 + 6 = 22")).toBeVisible();

  // The direct-digit-sum diagnostic must be visible and clearly labeled
  // non-canonical — it must never be presented as a second Life Path.
  await expect(page.getByText("Diagnostic (non-canonical)").first()).toBeVisible();
  await expect(page.getByText("1 + 8 + 0 + 7 + 1 + 9 + 8 + 6 = 40")).toBeVisible();
});
