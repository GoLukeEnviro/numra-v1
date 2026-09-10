import { test, expect, type Browser, type BrowserContext, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

/**
 * REALITY_CHECK_2 Phase 2 -- the REAL two-account journey.
 *
 * No page.route() anywhere. Every request goes through the real same-origin Next
 * proxy (/api/[...path]) to the real FastAPI + Postgres of the isolated
 * `numra-rc2` docker compose stack (scripts/rc2-e2e.sh). Two independent browser
 * contexts, one per user (A = inviter, B = redeemer).
 *
 * API-SETUP steps (explicitly marked): only the two account registrations, done
 * with page.request.post because no self-signup UI exists on this build (same as
 * system-journey.spec.ts). Everything the product claim rests on -- invitation,
 * redeem, consent grant/revoke, dual profile, relationship type, dissolve -- is a
 * real UI action.
 *
 * Run once per viewport project (desktop-1440x900, mobile-390x844); the target
 * size comes from the project metadata and is re-asserted from the live DOM
 * before any product assertion.
 */

const PASSWORD = "correct-horse-battery-staple-2026";
const uniqueEmail = (tag: string) =>
  `system-e2e-rc2-${tag}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;

const DEFAULT_SCOPE_LABELS = ["Kernzahlen", "Beziehungs-Einblicke", "Aktuelles Timing"];
const EXTENDED_SCOPE_LABELS = [
  "Privates Journal",
  "Private Aufgaben",
  "Privater Copilot",
  "Andere Beziehungen",
  "Lebens-Tracking",
];

test.setTimeout(360_000);

type Vp = { width: number; height: number };

function projectViewport(): { vp: Vp; isMobile: boolean; hasTouch: boolean } {
  const md = test.info().project.metadata as {
    viewport: Vp;
    isMobile: boolean;
    hasTouch: boolean;
  };
  return { vp: md.viewport, isMobile: md.isMobile, hasTouch: md.hasTouch };
}

function shotDir(): string {
  const dir = path.join("test-results", "rc2", test.info().project.name);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}
async function shoot(page: Page, name: string) {
  await page.screenshot({ path: path.join(shotDir(), `${name}.png`), fullPage: true });
}

/** Off-origin guard: the browser must only ever hit same-origin /api/*. */
function watchOrigin(page: Page, sink: string[]) {
  page.on("request", (req) => {
    const u = new URL(req.url());
    if (u.port === "58000" || u.port === "8000" || u.hostname === "api") sink.push(req.url());
  });
}

async function assertMeasuredViewport(page: Page, expected: Vp) {
  expect(page.viewportSize()).toEqual(expected);
  const real = await page.evaluate(() => ({ w: window.innerWidth, h: window.innerHeight }));
  // eslint-disable-next-line no-console
  console.log(`RC2_MEASURED_VIEWPORT project=${test.info().project.name} inner=${real.w}x${real.h}`);
  expect(real.w).toBe(expected.width);
  expect(real.h).toBe(expected.height);
}

async function registerViaApi(page: Page, email: string) {
  // ===== API-SETUP STEP: account creation (no self-signup UI on this build) =====
  const res = await page.request.post("/api/v1/auth/register", { data: { email, password: PASSWORD } });
  expect(res.status(), await res.text()).toBe(201);
}

async function loginViaUi(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("E-Mail").fill(email);
  await page.getByLabel("Passwort").fill(PASSWORD);
  await page.getByRole("button", { name: "Anmelden" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

async function createSelfProfileViaUi(page: Page, first: string, last: string, dob: string) {
  // The account's one SELF person + its calculation -- the dual profile only ever
  // reads a member's SELF person (people/new creates MANAGED_OTHER), so the
  // onboarding flow is the real UI path for this.
  await page.goto("/onboarding");
  await page.getByRole("button", { name: "Erstes Profil anlegen" }).click(); // welcome -> profile
  await page.getByLabel("Vorname(n) *").fill(first);
  await page.getByLabel("Nachname *").fill(last);
  await page.getByLabel("Geburtsdatum *").fill(dob);
  await page.locator("form").getByRole("button", { name: "Erstes Profil anlegen" }).click();
  await page.getByRole("button", { name: "Berechnung starten" }).click();
  await expect(page.getByRole("heading", { name: "Fertig" })).toBeVisible({ timeout: 60_000 });
}

/** The consent Card ("Von mir geteilt" / "Mit mir geteilt") as an isolated scope. */
function consentCard(page: Page, title: string) {
  return page
    .getByRole("heading", { name: title })
    .locator('xpath=ancestor::div[contains(@class,"rounded-xl")][1]');
}

async function assertDefaultConsentVisible(page: Page) {
  // Outgoing: exactly the 3 default scopes ON, the 5 extended OFF.
  const mine = consentCard(page, "Von mir geteilt");
  for (const label of DEFAULT_SCOPE_LABELS) {
    await expect(mine.getByRole("switch", { name: label })).toHaveAttribute("aria-checked", "true");
  }
  for (const label of EXTENDED_SCOPE_LABELS) {
    await expect(mine.getByRole("switch", { name: label })).toHaveAttribute("aria-checked", "false");
  }
  // Incoming: the 3 default scopes show the "Freigegeben" badge.
  const theirs = consentCard(page, "Mit mir geteilt");
  for (const label of DEFAULT_SCOPE_LABELS) {
    await expect(
      theirs.locator("div").filter({ hasText: new RegExp(`^${label}`) }).last().getByText("Freigegeben", { exact: true }),
    ).toBeVisible();
  }
}

function outgoingSwitch(page: Page, label: string) {
  return consentCard(page, "Von mir geteilt").getByRole("switch", { name: label });
}
function incomingRow(page: Page, label: string) {
  return consentCard(page, "Mit mir geteilt")
    .locator("div")
    .filter({ hasText: new RegExp(`^${label}`) })
    .last();
}

async function toggleOutgoing(page: Page, label: string, want: boolean) {
  const sw = outgoingSwitch(page, label);
  const now = (await sw.getAttribute("aria-checked")) === "true";
  if (now !== want) {
    await sw.click();
    await expect(sw).toHaveAttribute("aria-checked", String(want));
  }
}

test("RC2 two-account journey: connections/consent/dual-profile/type/dissolve over the UI", async ({
  browser,
}: {
  browser: Browser;
}) => {
  const { vp, isMobile, hasTouch } = projectViewport();
  const emailA = uniqueEmail("a");
  const emailB = uniqueEmail("b");
  const offOrigin: string[] = [];

  const ctxA: BrowserContext = await browser.newContext({ viewport: vp, isMobile, hasTouch });
  const ctxB: BrowserContext = await browser.newContext({ viewport: vp, isMobile, hasTouch });
  const A = await ctxA.newPage();
  const B = await ctxB.newPage();
  watchOrigin(A, offOrigin);
  watchOrigin(B, offOrigin);

  try {
    await registerViaApi(A, emailA);
    await registerViaApi(B, emailB);

    await loginViaUi(A, emailA);
    await loginViaUi(B, emailB);

    // Measured-viewport gate -- BEFORE any product assertion, per context.
    await assertMeasuredViewport(A, vp);
    await assertMeasuredViewport(B, vp);

    await createSelfProfileViaUi(A, "Lukas", "Springer", "1986-07-18");
    await createSelfProfileViaUi(B, "Anna", "Berger", "1990-03-14");

    // --- A creates a LINK invitation via the UI, reads the real redeem_url ---
    await A.goto("/connections/invite");
    await expect(A.getByRole("radio", { name: "Link" })).toHaveAttribute("aria-checked", "true");
    await A.getByRole("button", { name: "Weiter" }).click();
    await expect(A.getByRole("heading", { name: "Einladung erstellt" })).toBeVisible();
    const redeemInput = A.locator("input[readonly]").first();
    await expect(redeemInput).toBeVisible();
    const redeemUrl = await redeemInput.inputValue();
    expect(redeemUrl).toMatch(/^http:\/\/localhost:3100\/connections\/redeem\?token=/);
    const copyBtn = A.getByRole("button", { name: /Kopieren/ });
    await expect(copyBtn).toBeInViewport();
    await expect(copyBtn).toBeEnabled();
    await shoot(A, "01-invitation-created");

    // --- B opens the UNMODIFIED redeem_url in its own context ---
    await B.goto(redeemUrl);
    await expect(B.getByText("Methode", { exact: false }).first()).toBeVisible();
    const acceptBtn = B.getByRole("button", { name: "Annehmen" });
    await expect(acceptBtn).toBeInViewport();
    await shoot(B, "02-redeem-preview");
    await acceptBtn.click();
    await expect(B).toHaveURL(/\/workspaces\/[0-9a-f-]{36}\/consent/);
    const workspaceId = B.url().match(/workspaces\/([0-9a-f-]{36})/)![1];

    // --- Standard consent: 3 default scopes, both directions, both users ---
    await assertDefaultConsentVisible(B);
    await shoot(B, "03-consent-b-after-redeem");

    await A.goto("/connections");
    await expect(consentCard(A, "Aktive Verbindungen")).toBeVisible();
    await A.getByRole("link", { name: "Freigaben öffnen" }).click();
    await expect(A).toHaveURL(new RegExp(`/workspaces/${workspaceId}/consent`));
    await assertDefaultConsentVisible(A);
    await shoot(A, "04-consent-a-after-redeem");

    // --- Dual profile COMPLETE (consent both ways) ---
    for (const [p, tag] of [
      [A, "a"],
      [B, "b"],
    ] as const) {
      await p.goto(`/workspaces/${workspaceId}`);
      const section = p.locator("section", { has: p.getByText("Zwei Seiten") });
      await expect(section).toBeVisible();
      // Both sides render real core numbers; the degraded hint appears nowhere.
      await expect(p.getByText("hat die Kernzahlen noch nicht freigegeben.")).toHaveCount(0);
      await expect(section.getByText("Life Path")).toHaveCount(2);
      await expect(section.getByText("Deine Seite")).toBeVisible();
      await shoot(p, `05-dual-profile-full-${tag}`);
    }

    // --- A revokes CORE_NUMEROLOGY (A -> B). B has its overview OPEN. ---
    await A.goto(`/workspaces/${workspaceId}/consent`);
    await toggleOutgoing(A, "Kernzahlen", false);

    // Already-open counterpart: B reloads the overview it was left on -> degraded, no error.
    await B.reload();
    await expect(B.getByText("hat die Kernzahlen noch nicht freigegeben.")).toBeVisible();
    // Degraded, not errored: the overview still renders and no "went wrong" state.
    await expect(B.getByText("Deine Seite")).toBeVisible();
    await expect(B.getByText(/Something went wrong|Etwas ist schief/i)).toHaveCount(0);
    await shoot(B, "06-dual-profile-degraded-b");

    // B's consent page reflects the revoke on next protected fetch.
    await B.goto(`/workspaces/${workspaceId}/consent`);
    await expect(incomingRow(B, "Kernzahlen").getByText("Nicht freigegeben", { exact: true })).toBeVisible();

    // Opposite direction UNTOUCHED: B -> A CORE_NUMEROLOGY still granted.
    await expect(outgoingSwitch(B, "Kernzahlen")).toHaveAttribute("aria-checked", "true");
    await A.goto(`/workspaces/${workspaceId}/consent`);
    await expect(incomingRow(A, "Kernzahlen").getByText("Freigegeben", { exact: true })).toBeVisible();
    await A.goto(`/workspaces/${workspaceId}`);
    await expect(A.getByText("hat die Kernzahlen noch nicht freigegeben.")).toHaveCount(0);
    await expect(A.getByText("Life Path").first()).toBeVisible();

    // --- Re-grant CORE_NUMEROLOGY (A -> B) via the toggle: the previously revoked
    // grant is reactivated (fix #45), B regains access on the next fetch. ---
    await A.goto(`/workspaces/${workspaceId}/consent`);
    await toggleOutgoing(A, "Kernzahlen", true);
    await B.goto(`/workspaces/${workspaceId}/consent`);
    await expect(incomingRow(B, "Kernzahlen").getByText("Freigegeben", { exact: true })).toBeVisible();
    await B.goto(`/workspaces/${workspaceId}`);
    await expect(B.getByText("hat die Kernzahlen noch nicht freigegeben.")).toHaveCount(0);
    await expect(
      B.locator("section", { has: B.getByText("Zwei Seiten") }).getByText("Life Path"),
    ).toHaveCount(2);
    await shoot(B, "06a-core-numerology-regranted-b");

    // --- Independent grant + revoke via the consent UI, both directions ---
    // B -> A: PRIVATE_JOURNAL
    await B.goto(`/workspaces/${workspaceId}/consent`);
    await toggleOutgoing(B, "Privates Journal", true);
    await A.goto(`/workspaces/${workspaceId}/consent`);
    await expect(incomingRow(A, "Privates Journal").getByText("Freigegeben", { exact: true })).toBeVisible();
    await B.goto(`/workspaces/${workspaceId}/consent`);
    await toggleOutgoing(B, "Privates Journal", false);
    await A.goto(`/workspaces/${workspaceId}/consent`);
    await expect(incomingRow(A, "Privates Journal").getByText("Nicht freigegeben", { exact: true })).toBeVisible();
    // A -> B: PRIVATE_TASKS (opposite direction, independent)
    await A.goto(`/workspaces/${workspaceId}/consent`);
    await toggleOutgoing(A, "Private Aufgaben", true);
    await B.goto(`/workspaces/${workspaceId}/consent`);
    await expect(incomingRow(B, "Private Aufgaben").getByText("Freigegeben", { exact: true })).toBeVisible();
    // B -> A PRIVATE_TASKS stays untouched by A's grant (per-direction).
    await expect(outgoingSwitch(B, "Private Aufgaben")).toHaveAttribute("aria-checked", "false");
    await A.goto(`/workspaces/${workspaceId}/consent`);
    await toggleOutgoing(A, "Private Aufgaben", false);
    await B.goto(`/workspaces/${workspaceId}/consent`);
    await expect(incomingRow(B, "Private Aufgaben").getByText("Nicht freigegeben", { exact: true })).toBeVisible();
    await shoot(A, "06b-consent-grant-revoke-both-directions");

    // --- Relationship type: explicit Save + persistence across reload ---
    await A.goto(`/workspaces/${workspaceId}`);
    const typeSelect = A.getByLabel("Beziehungstyp");
    await typeSelect.selectOption("PARTNER");
    const saveBtn = A.getByRole("button", { name: "Speichern" });
    await expect(saveBtn).toBeInViewport();
    await saveBtn.click();
    await expect(A.getByText("Gespeichert", { exact: true })).toBeVisible();
    await A.reload();
    await expect(A.getByLabel("Beziehungstyp")).toHaveValue("PARTNER");
    await A.goto("/workspaces");
    await expect(A.getByText("Partner", { exact: true }).first()).toBeVisible();
    await shoot(A, "07-relationship-type-partner");

    // --- WEB-05: Dynamics tab -- real (non-mocked) relationship + shadow analysis.
    // Preconditions all met here: workspace ACTIVE, type PARTNER, both members have
    // a SELF person + calculation, RELATIONSHIP_INSIGHTS granted both ways (never
    // revoked above). Jobs run in the real analysis-worker (NUMRA_LLM_PROVIDER=mock
    // -> deterministic). Desktop only: the async job flow (POST -> poll -> terminal
    // render) is viewport-independent, and running two real jobs under mobile
    // emulation roughly quadruples this journey's wall-clock for no extra signal --
    // the /dynamics responsive layout at 390x844 is covered by the mocked
    // pr-web-05-visual-baseline suite.
    if (test.info().project.name === "desktop-1440x900") {
      await A.goto(`/workspaces/${workspaceId}`);
      // The hub links to /dynamics from both a nav tab (accessible name exactly
      // "Dynamiken") and a hub card (longer name) -- exact-match the tab.
      await A.getByRole("link", { name: "Dynamiken", exact: true }).click();
      await expect(A).toHaveURL(new RegExp(`/workspaces/${workspaceId}/dynamics`));
      await expect(A.getByRole("heading", { name: "Dynamiken", exact: true })).toBeVisible();

      const relSection = A.locator("section", {
        has: A.getByText("Beziehungsanalyse", { exact: true }),
      });
      await relSection.getByRole("button", { name: "Beziehungsanalyse starten" }).click();
      // Job -> analysis-worker -> COMPLETE -> UI re-fetches the full body and renders.
      const relProvenance = relSection.getByRole("button", { name: "Herkunft", exact: true });
      await expect(relProvenance.first()).toBeVisible({ timeout: 120_000 });
      await expect(relSection.getByText("Berechnungs-Version")).toBeVisible();
      // Provenance disclosure reveals the source groups (empty ones included).
      await relProvenance.first().click();
      await expect(relSection.getByText(/Kanonische Werte|Wissenseinträge/).first()).toBeVisible();

      // Shadow: start the real job, assert the UI settles into a correct TERMINAL
      // render regardless of outcome. With the RC2 fixture profiles (one is the
      // canonical master-22 Life Path) the shadow pipeline currently raises "No
      // shadow interaction rule found for theme" -- a backend knowledge-data gap
      // (rules.yaml covers Life Path 1-9 only), out of scope for this frontend PR
      // -> the section must show the FAILED view with the error_code verbatim +
      // a retry. A non-master profile pair reaches the COMPLETE view instead.
      const shadowSection = A.locator("section", {
        has: A.getByText("Schattendynamik", { exact: true }),
      });
      await shadowSection.getByRole("button", { name: "Schattendynamik starten" }).click();
      const shadowComplete = shadowSection.getByRole("heading", { name: "Person A", exact: true });
      const shadowFailed = shadowSection.getByRole("heading", { name: "Analyse fehlgeschlagen" });
      await expect(shadowComplete.or(shadowFailed).first()).toBeVisible({ timeout: 120_000 });
      if (await shadowFailed.isVisible()) {
        await expect(shadowSection.getByText(/gemeldet vom Erzeugungs-Job/)).toBeVisible();
        await expect(
          shadowSection.getByRole("button", { name: "Neue Analyse starten" }),
        ).toBeVisible();
      } else {
        await expect(
          shadowSection.getByRole("heading", { name: "Person B", exact: true }),
        ).toBeVisible();
        await expect(shadowSection.getByRole("heading", { name: "Musterintensität" })).toBeVisible();
      }
      // pattern_intensity is a text label, never a progress bar / score (the job
      // progress bar lives in the pending view, not here).
      await expect(shadowSection.locator('[role="progressbar"]')).toHaveCount(0);
      // No screenshot here on purpose: the mock LLM provider echoes the raw
      // grounding facts as "prose", so a fullPage shot of a real-stack analysis is
      // an unreadable debug wall, not evidence. The rendered look is proven by the
      // curated-fixture pr-web-05-visual-baseline suite; here only the structure
      // (sections, provenance disclosure, meta footer, terminal handling) matters.

      // Second context reaches /dynamics without error and reads the same rows
      // (per-workspace, IDOR-gated GET).
      await B.goto(`/workspaces/${workspaceId}/dynamics`);
      await expect(B.getByRole("heading", { name: "Dynamiken", exact: true })).toBeVisible();
      await expect(B.getByText(/Something went wrong|Etwas ist schief/i)).toHaveCount(0);
      await expect(
        B.locator("section", { has: B.getByText("Beziehungsanalyse", { exact: true }) }).getByText(
          "Berechnungs-Version",
        ),
      ).toBeVisible({ timeout: 30_000 });
    }

    // --- Dissolve via the UI ---
    await A.goto("/connections");
    await A.getByRole("button", { name: "Verbindung auflösen" }).click();
    await A.getByRole("button", { name: "Endgültig auflösen" }).click();
    await expect(A.getByRole("button", { name: "Verbindung auflösen" })).toHaveCount(0);

    // Read-only after dissolution: UI shows the dissolved state, GET still works.
    await A.goto(`/workspaces/${workspaceId}`);
    await expect(A.getByText("Aufgelöst am", { exact: false })).toBeVisible();
    await expect(A.getByText("Workspace aufgelöst", { exact: true })).toBeVisible();
    await expect(A.getByText(/Something went wrong|Etwas ist schief/i)).toHaveCount(0);
    await shoot(A, "08-workspace-dissolved-readonly");

    // Mutation lock, same-origin: PATCH -> 409 WORKSPACE_DISSOLVED, GET -> 200.
    const csrf = (await ctxA.cookies()).find((c) => c.name === "numra_csrf")?.value ?? "";
    const patchRes = await A.request.patch(`/api/v1/workspaces/${workspaceId}`, {
      headers: { "x-csrf-token": csrf },
      data: { relationship_type: "WORK" },
    });
    expect(patchRes.status()).toBe(409);
    expect((await patchRes.json()).code).toBe("WORKSPACE_DISSOLVED");
    const getRes = await A.request.get(`/api/v1/workspaces/${workspaceId}`);
    expect(getRes.status()).toBe(200);

    expect(offOrigin, "browser must only call same-origin /api/*").toEqual([]);
    // eslint-disable-next-line no-console
    console.log(`RC2_JOURNEY_OK project=${test.info().project.name} workspace=${workspaceId}`);
  } finally {
    await ctxA.close();
    await ctxB.close();
  }
});
