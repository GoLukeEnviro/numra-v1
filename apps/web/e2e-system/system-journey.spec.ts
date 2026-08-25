import { test, expect } from "@playwright/test";

/**
 * The REAL system journey — no page.route() interception anywhere in this file.
 * Every request the browser makes goes through the real same-origin proxy
 * (/api/[...path]/route.ts) to a real FastAPI instance, backed by a real Postgres
 * database, with a real report worker consuming the job queue
 * (NUMRA_LLM_PROVIDER=mock is the explicit, non-implicit provider choice for
 * deterministic test content — see numra_api.services.llm_factory) and the real
 * internal PDF microservice (Playwright/Chromium) rendering the exported file.
 *
 * Prerequisites this spec assumes are already running (see
 * specs/evidence/system-e2e.md for the exact commands): Postgres, Redis, the PDF
 * service, a FastAPI instance, and a worker process, all pointed at the same
 * dedicated database. playwright.system.config.ts starts only the Next.js server
 * itself, pointed at that FastAPI instance via API_INTERNAL_URL.
 *
 * One long, ordered journey (not many small tests) because most of it is
 * necessarily sequential: nothing to compare exists before two people are created,
 * nothing to export exists before a report completes, and delete-all is only
 * meaningful to verify once everything above it exists.
 */

function uniqueEmail(): string {
  return `system-e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

const PASSWORD = "correct-horse-battery-staple-2026";

// Generous enough to cover both generous per-step waits (report generation up to
// 60s, PDF export up to 150s -- see the matching comment at the Download-link wait
// below) landing back-to-back in a worst case, plus every other step, with real
// headroom left over.
test.setTimeout(300_000);

test("real system journey: login through delete-all against the live stack", async ({ page }) => {
  const email = uniqueEmail();

  // Same-origin proof (release-closure Gate C §15): the browser must never call the
  // backend directly -- only same-origin /api/* through the Next.js proxy. Collected
  // for the whole journey below, asserted once at the end.
  const offOriginRequests: string[] = [];
  page.on("request", (req) => {
    const url = new URL(req.url());
    if (url.port === "8000" || url.hostname === "api" || url.port === "8010") {
      offOriginRequests.push(req.url());
    }
  });

  // 0. Register a fresh account directly against the real API (no registration UI
  // exists — self-signup is enabled only for this dedicated e2e instance).
  // page.request (not the standalone `request` fixture) so the session cookie the
  // upcoming login sets is shared with every subsequent request.get()/post() call
  // below — that shared cookie jar is what makes the post-delete auth checks mean
  // anything.
  const registerResponse = await page.request.post("/api/v1/auth/register", {
    data: { email, password: PASSWORD },
  });
  expect(registerResponse.status(), await registerResponse.text()).toBe(201);

  // 1. Log in through the real UI/API.
  await page.goto("/login");
  await page.getByLabel("E-Mail").fill(email);
  await page.getByLabel("Passwort").fill(PASSWORD);
  await page.getByRole("button", { name: "Anmelden" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  // 2. Create the first person (Lukas Springer — the pinned golden fixture) and let
  // its calculation run for real, through the deterministic engine.
  await page.getByRole("link", { name: "Neues Profil" }).first().click();
  await expect(page).toHaveURL(/\/people\/new$/);

  await page.getByLabel("Vorname(n) *").fill("Lukas");
  await page.getByLabel("Nachname *").fill("Springer");
  await page.getByLabel("Geburtsdatum *").fill("1986-07-18");
  await page.getByLabel("Geburtszeit", { exact: true }).fill("06:00");
  await page.getByLabel("Zeitgenauigkeit").selectOption("exact");
  await page.getByLabel("Geburtsort").fill("Meerbusch");
  await page.getByLabel("Ländercode").fill("DE");
  await page.getByRole("button", { name: /Profil anlegen & berechnen/i }).click();

  await expect(page).toHaveURL(/\/analysis\/[0-9a-f-]{36}$/);
  const calculationIdA = page.url().split("/analysis/")[1];
  await expect(page.getByRole("heading", { name: "Lukas Springer" })).toBeVisible();

  // Golden values (canon-spec.md, pinned) — genuinely computed by the real
  // deterministic engine running behind the real API, not fixture data.
  await expect(page.getByText("22/4", { exact: true }).first()).toBeVisible(); // Life Path
  await expect(page.getByText("62/8", { exact: true }).first()).toBeVisible(); // Expression
  await expect(page.getByText("18/9", { exact: true }).first()).toBeVisible(); // Soul Urge
  await expect(page.getByText("44/8", { exact: true }).first()).toBeVisible(); // Personality
  await expect(page.getByText(/Master Number 22/i).first()).toBeVisible();

  await page.getByRole("tab", { name: "Rechen-Inspektor" }).click();
  await expect(page.getByText("Day: 18 → 9")).toBeVisible();
  await expect(page.getByText("9 + 7 + 6 = 22")).toBeVisible();

  // 3. Dashboard and Today both load against the real backend without error.
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.goto("/today");
  await expect(page.getByRole("heading", { name: "Heute" })).toBeVisible();
  // With exactly one profile so far, the timing view renders directly (no picker).
  await expect(page.getByText(/Personal (Year|Month|Day)/i).first()).toBeVisible({
    timeout: 15_000,
  });

  // 4. Generate a real long-form report: real job enqueued, real worker claims and
  // processes it (NUMRA_LLM_PROVIDER=mock), real polling from the browser.
  await page.goto(`/analysis/${calculationIdA}`);
  await page.getByLabel("Quick", { exact: false }).first().check();
  await page.getByRole("button", { name: "Bericht erzeugen" }).click();

  await expect(page).toHaveURL(/\/reports\/[0-9a-f-]{36}$/);
  const reportId = page.url().split("/reports/")[1];

  // The report reader only renders once the job is COMPLETE — this wait is the real
  // proof the worker actually claimed and finished the job against a live database,
  // not an instantaneous mocked response.
  await expect(page.getByRole("heading", { name: "Export" })).toBeVisible({ timeout: 60_000 });

  // 5. Export a real PDF: POST /v1/exports is synchronous and blocks on a genuine
  // Playwright/Chromium render in the internal PDF service, which lazily launches
  // Chromium on its own first request (apps/pdf/src/server.js) -- a cold start that
  // can land inside THIS request under real multi-container CI load. The server's
  // own PdfServiceClient timeout (numra_api.config.pdf_render_timeout_seconds) is
  // 120s -- this wait must clear that with real margin, or a genuine slow-but-real
  // render gets marked "failed" server-side before the client would ever see it as
  // slow-but-successful.
  await page.getByRole("button", { name: "PDF exportieren" }).click();
  await expect(page.getByRole("link", { name: /Herunterladen/i })).toBeVisible({ timeout: 150_000 });
  const downloadHref = await page.getByRole("link", { name: /Herunterladen/i }).getAttribute("href");
  expect(downloadHref).toBeTruthy();

  const pdfResponse = await page.request.get(downloadHref!);
  expect(pdfResponse.status()).toBe(200);
  expect(pdfResponse.headers()["content-type"]).toContain("application/pdf");
  const pdfBytes = await pdfResponse.body();
  expect(pdfBytes.subarray(0, 5).toString("latin1")).toBe("%PDF-");
  expect(pdfBytes.byteLength).toBeGreaterThan(1000);

  // 6. Create a second person, with a current name and preferred name, to exercise
  // the Identity Timeline as more than a single birth-name entry.
  await page.goto("/people/new");
  await page.getByLabel("Vorname(n) *").fill("Anna");
  await page.getByLabel("Nachname *").fill("Berger");
  await page.getByLabel("Geburtsdatum *").fill("1990-03-14");
  await page.getByLabel("Aktuelle(r) Vorname(n)").fill("Anna");
  await page.getByLabel("Aktueller Nachname").fill("Weber");
  await page.getByLabel("Rufname").fill("Annie");
  await page.getByRole("button", { name: /Profil anlegen & berechnen/i }).click();

  await expect(page).toHaveURL(/\/analysis\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { name: "Anna Berger" })).toBeVisible();

  await page.goto("/people");
  // The People tile shows the preferred name ("Annie") when one is set, not the
  // birth name — personDisplayName() prioritizes it deliberately.
  await page.getByRole("link", { name: /Annie/i }).click();
  await expect(page.getByRole("heading", { name: "Identität" })).toBeVisible();
  await expect(page.getByText("Geburtsname", { exact: true })).toBeVisible();
  await expect(page.getByText("Aktueller Name", { exact: true })).toBeVisible();
  // "Rufname" labels both the identity-timeline entry and (when the server has also
  // recorded a "preferred" history row) the matching badge in the "Erfasste
  // Historie" list below -- de/app.ts intentionally reuses the same word for
  // app.identity.preferredLabel and app.identity.kindPreferred, so this may
  // legitimately match more than one element.
  await expect(page.getByText("Rufname", { exact: true }).first()).toBeVisible();
  // Two lists render "Annie" now (V1.5 Epic C added a second, server-authoritative
  // "Recorded history" log alongside the original current-state timeline) -- scope
  // to the current-identity one, which is what this assertion is actually about.
  await expect(
    page.getByRole("list", { name: "Identität" }).getByText("Annie", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Für Kernzahlen verwendet")).toBeVisible();

  // 7. Relationship comparison: V1.5 Epic E made this select by PERSON, not by a
  // pasted calculation UUID -- the backend resolves each person's latest
  // calculation itself. Both people created above appear by their real display
  // name (personDisplayName() prioritizes the preferred name, hence "Annie").
  await page.goto("/relationships");
  await page.getByLabel("Erste Person").selectOption({ label: "Lukas Springer" });
  await page.getByLabel("Zweite Person").selectOption({ label: "Annie" });
  await page.getByRole("button", { name: "Vergleichen" }).click();

  await expect(page).toHaveURL(/\/relationships\/[0-9a-f-]{36}$/);
  await expect(page.getByText(/Kompatibilitäts-Prozentsatz/i)).toBeVisible();
  // The canon-spec prohibition holds against the live comparison output too: no bare
  // percentage sign appears anywhere on the rendered comparison.
  await expect(page.locator("body")).not.toContainText("%");

  // 8. Delete-All: real password-confirmed deletion against the live account.
  await page.goto("/settings/privacy");
  await page.getByRole("button", { name: "Mein Konto löschen" }).click();
  await page.getByLabel("Mit deinem Passwort bestätigen").fill(PASSWORD);
  await page.getByRole("button", { name: "Alles endgültig löschen" }).click();

  await expect(page).toHaveURL(/\/login$/, { timeout: 15_000 });

  // The server-side session must be genuinely gone, not just the client's local
  // belief about it: the same session cookie (still held by this browser context)
  // must now be rejected.
  const meAfterDelete = await page.request.get("/api/v1/auth/me");
  expect(meAfterDelete.status()).toBe(401);

  // The now-deleted session can no longer authenticate a download either (the
  // export row and its file itself are gone too — verified independently, directly
  // on disk, by the shell script that runs this spec; an authenticated request
  // could not tell "row gone" apart from "session gone" once both are true).
  const downloadAfterDelete = await page.request.get(downloadHref!);
  expect(downloadAfterDelete.status()).toBe(401);

  // A second registration with the same email must succeed — proof the account row
  // itself, not just its session, was removed.
  const reRegisterResponse = await page.request.post("/api/v1/auth/register", {
    data: { email, password: PASSWORD },
  });
  expect(reRegisterResponse.status(), await reRegisterResponse.text()).toBe(201);

  expect(
    offOriginRequests,
    "the browser must never call the backend directly -- only same-origin /api/* through the Next.js proxy",
  ).toEqual([]);

  console.log(`SYSTEM_E2E_REPORT_ID=${reportId}`);
});
