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
    await expect
      .poll(() => A.evaluate(async () => (await navigator.serviceWorker.getRegistrations()).length))
      .toBeGreaterThan(0);

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

    // --- WEB-05: Dynamics tab -- real (non-mocked) analysis against the live
    // analysis-worker (NUMRA_LLM_PROVIDER=mock -> deterministic). Preconditions all
    // met: workspace ACTIVE, type PARTNER, both members have a SELF person +
    // calculation, RELATIONSHIP_INSIGHTS granted both ways. Note: user A's profile
    // (Lukas Springer, 1986-07-18) resolves to the canonical MASTER-22 Life Path --
    // this exercises the master-number shadow path that used to raise
    // UNEXPECTED_ERROR before the shadow-interaction rules covered 11/22/33.
    await A.goto(`/workspaces/${workspaceId}`);
    // Two links to /dynamics on the hub (nav tab, name exactly "Dynamiken", and a
    // longer hub card) -- exact-match the tab.
    await A.getByRole("link", { name: "Dynamiken", exact: true }).click();
    await expect(A).toHaveURL(new RegExp(`/workspaces/${workspaceId}/dynamics`));
    await expect(A.getByRole("heading", { name: "Dynamiken", exact: true })).toBeVisible();

    const isDesktop = test.info().project.name === "desktop-1440x900";
    const relSection = A.locator("section", {
      has: A.getByText("Beziehungsanalyse", { exact: true }),
    });
    if (isDesktop) {
      // Relationship analysis: full success path. Desktop only -- the mock provider
      // echoes the raw grounding facts as "prose", producing a very tall DOM that
      // is slow to render under mobile emulation for no extra signal (the responsive
      // layout is covered by the mocked pr-web-05-visual-baseline suite).
      await relSection.getByRole("button", { name: "Beziehungsanalyse starten" }).click();
      const relProvenance = relSection.getByRole("button", { name: "Herkunft", exact: true });
      await expect(relProvenance.first()).toBeVisible({ timeout: 120_000 });
      await expect(relSection.getByText("Berechnungs-Version")).toBeVisible();
      await relProvenance.first().click();
      await expect(relSection.getByText(/Kanonische Werte|Wissenseinträge/).first()).toBeVisible();
    }

    // Shadow dynamics: MUST reach COMPLETE for these (valid, master-22) profiles --
    // on BOTH viewports. A FAILED outcome here is a regression of the master-number
    // rule coverage, not an acceptable result.
    const shadowSection = A.locator("section", {
      has: A.getByText("Schattendynamik", { exact: true }),
    });
    await shadowSection.getByRole("button", { name: "Schattendynamik starten" }).click();
    await expect(
      shadowSection.getByRole("heading", { name: "Person A", exact: true }),
    ).toBeVisible({ timeout: 150_000 });
    await expect(
      shadowSection.getByRole("heading", { name: "Person B", exact: true }),
    ).toBeVisible();
    await expect(shadowSection.getByRole("heading", { name: "Musterintensität" })).toBeVisible();
    await expect(
      shadowSection.getByRole("heading", { name: "Empfohlene Mikro-Schritte" }),
    ).toBeVisible();
    await expect(shadowSection.getByText("Berechnungs-Version")).toBeVisible();
    // A/B attribution: both person blocks carry their own provenance disclosure.
    await expect(shadowSection.getByRole("button", { name: "Herkunft", exact: true }).first())
      .toBeVisible();
    // pattern_intensity is a text label, never a progress bar / score.
    await expect(shadowSection.locator('[role="progressbar"]')).toHaveCount(0);
    await expect(shadowSection).not.toContainText("%");
    // No screenshot: the mock LLM provider echoes raw grounding facts into the
    // interaction-pattern statement, so a fullPage shot is an unreadable debug
    // wall. The structural assertions above (both person blocks, provenance,
    // meta footer, no progressbar, COMPLETE reached) are the evidence; the
    // rendered look is proven by the curated pr-web-05-visual-baseline suite.

    // Second context reads the same COMPLETE shadow analysis read-only (per
    // workspace, IDOR-gated GET), no error.
    await B.goto(`/workspaces/${workspaceId}/dynamics`);
    await expect(B.getByRole("heading", { name: "Dynamiken", exact: true })).toBeVisible();
    await expect(B.getByText(/Something went wrong|Etwas ist schief/i)).toHaveCount(0);
    await expect(
      B.locator("section", { has: B.getByText("Schattendynamik", { exact: true }) }).getByRole(
        "heading",
        { name: "Person A", exact: true },
      ),
    ).toBeVisible({ timeout: 30_000 });

    // --- WEB-06b: explicit two-account check-in round, entirely through the UI. ---
    await A.goto(`/workspaces/${workspaceId}/checkins`);
    await A.getByRole("button", { name: "Runde starten" }).click();
    await A.getByRole("button", { name: "Jetzt verbindlich starten" }).click();
    await expect(A.getByRole("heading", { name: "Deine Sicht heute" })).toBeVisible();
    for (const group of await A.getByRole("radiogroup").all()) {
      await group.getByRole("radio", { name: "7", exact: true }).click();
    }
    await A.getByRole("button", { name: "Antworten verbindlich abgeben" }).click();
    await expect(A.getByRole("heading", { name: "Deine Seite ist abgegeben" })).toBeVisible();

    await B.goto(`/workspaces/${workspaceId}/checkins`);
    await expect(B.getByRole("heading", { name: "Deine Sicht heute" })).toBeVisible();
    for (const group of await B.getByRole("radiogroup").all()) {
      await group.getByRole("radio", { name: "5", exact: true }).click();
    }
    await B.getByRole("button", { name: "Antworten verbindlich abgeben" }).click();
    await expect(B.getByRole("heading", { name: "Auswertung dieser Runde" })).toBeVisible();
    await expect(B.getByText("Abstand", { exact: true }).first()).toBeVisible();
    await expect(B.getByText(/Partner-Rohwert/i)).toHaveCount(0);

    await A.getByRole("button", { name: "Status aktualisieren" }).click();
    await expect(A.getByRole("heading", { name: "Auswertung dieser Runde" })).toBeVisible();
    await expect(A.getByRole("button", { name: "Neue Runde starten" })).toBeVisible();
    await shoot(A, "08-checkin-analyzed");

    // --- WEB-07: A proposes a task; B explicitly accepts it; both then see the
    // same ACTIVE shared artifact. No private-task consent is involved.
    await A.goto(`/workspaces/${workspaceId}/tasks`);
    await A.getByRole("button", { name: "Aufgabe anlegen" }).click();
    await A.getByLabel("Aufgabentyp").selectOption("FOR_PARTNER_PROPOSED");
    await A.getByLabel("Titel").fill("Sonntag gemeinsam spazieren gehen");
    await A.getByLabel("Beschreibung (optional)").fill("Eine Stunde ohne feste Agenda.");
    await A.getByRole("button", { name: "Anlegen" }).click();
    await expect(A.getByText("Wartet auf Annahme", { exact: true })).toBeVisible();
    await expect(A.getByRole("button", { name: "Annehmen" })).toHaveCount(0);

    await B.goto(`/workspaces/${workspaceId}/tasks`);
    await expect(B.getByText("Sonntag gemeinsam spazieren gehen", { exact: true })).toBeVisible();
    const acceptTask = B.getByRole("button", { name: "Annehmen" });
    await acceptTask.evaluate((element) => element.scrollIntoView({ block: "center" }));
    const acceptBox = await acceptTask.boundingBox();
    expect(acceptBox).not.toBeNull();
    await B.mouse.click(acceptBox!.x + acceptBox!.width / 2, acceptBox!.y + acceptBox!.height / 2);
    await expect(B.getByText("Aktiv", { exact: true }).last()).toBeVisible();
    await expect(B.getByRole("button", { name: "Als erledigt markieren" })).toBeVisible();

    await A.reload();
    await expect(A.getByText("Aktiv", { exact: true }).last()).toBeVisible();
    await expect(A.getByRole("button", { name: "Als erledigt markieren" })).toBeVisible();
    await shoot(A, "09-task-accepted");

    // --- WEB-08: A creates a roadmap with a review point and links the accepted
    // shared task. B reads the same artifacts from an independent session.
    await A.goto(`/workspaces/${workspaceId}/roadmaps`);
    await A.getByRole("button", { name: "Roadmap anlegen" }).click();
    await A.getByLabel("Titel").fill("Unser nächster gemeinsamer Abschnitt");
    await A.getByLabel("Zeitraum").selectOption("30_DAY");
    await A.locator("form").getByRole("button", { name: "Anlegen" }).click();
    await expect(A.getByText("Unser nächster gemeinsamer Abschnitt", { exact: true })).toBeVisible();
    await A.getByRole("button", { name: "Schritt hinzufügen" }).click();
    const stepForm = A.locator("form", { has: A.getByLabel("Art des Schritts") });
    await stepForm.getByLabel("Titel").fill("Gemeinsam zurückblicken");
    await stepForm.getByLabel("Beschreibung").fill("Was hat uns in diesem Monat gutgetan?");
    await stepForm.getByLabel("Art des Schritts").selectOption("REVIEW_POINT");
    await stepForm.getByRole("button", { name: "Anlegen" }).click();
    await expect(A.getByText("Gemeinsam zurückblicken", { exact: true })).toBeVisible();
    await A.getByLabel("Aufgabe zuordnen").selectOption({ label: "Sonntag gemeinsam spazieren gehen" });
    await expect(A.getByText(/Sonntag gemeinsam spazieren gehen/).last()).toBeVisible();

    await B.goto(`/workspaces/${workspaceId}/roadmaps`);
    await expect(B.getByText("Unser nächster gemeinsamer Abschnitt", { exact: true })).toBeVisible();
    await expect(B.getByText("Gemeinsam zurückblicken", { exact: true })).toBeVisible();
    await shoot(B, "10-web08-roadmap-shared");

    // A writes a private reflection in the private person workspace, then shares
    // an explicit immutable copy. B never receives access to the private source.
    await A.goto(`/workspaces/${workspaceId}/reflections`);
    await A.getByRole("link", { name: "Zum privaten Workspace" }).click();
    await A.getByRole("button", { name: "Neuer Eintrag", exact: true }).click();
    await A.getByLabel("Inhalt").fill("Ich wünsche mir mehr ruhige Zeit für unsere Gespräche.");
    await A.getByRole("button", { name: "Speichern", exact: true }).click();
    await expect(A.getByText("Ich wünsche mir mehr ruhige Zeit für unsere Gespräche.", { exact: true })).toBeVisible();
    await A.goto(`/workspaces/${workspaceId}/reflections`);
    await A.getByRole("button", { name: "Private Reflexion auswählen" }).click();
    await A.getByLabel("Deine private Reflexion").selectOption({ index: 1 });
    await expect(A.getByRole("heading", { name: "Vorschau der geteilten Kopie" })).toBeVisible();
    await A.getByRole("button", { name: "Kopie jetzt teilen" }).click();
    await expect(A.getByText("Ich wünsche mir mehr ruhige Zeit für unsere Gespräche.", { exact: true })).toBeVisible();
    await B.goto(`/workspaces/${workspaceId}/reflections`);
    await expect(B.getByText("Ich wünsche mir mehr ruhige Zeit für unsere Gespräche.", { exact: true })).toBeVisible();
    await expect(B.getByRole("button", { name: "Geteilte Kopie entfernen" })).toHaveCount(0);
    await shoot(B, "11-web08-explicit-shared-reflection");

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

    await A.goto(`/workspaces/${workspaceId}/checkins`);
    await expect(A.getByRole("heading", { name: "Historische Ansicht" })).toBeVisible();
    await expect(A.getByRole("heading", { name: "Auswertung dieser Runde" })).toBeVisible();
    await expect(A.getByRole("button", { name: /Runde starten/ })).toHaveCount(0);
    await expect(A.getByRole("button", { name: "Frage hinzufügen" })).toHaveCount(0);

    await A.goto(`/workspaces/${workspaceId}/tasks`);
    await expect(A.getByRole("heading", { name: "Historische Ansicht" })).toBeVisible();
    await expect(A.getByText("Sonntag gemeinsam spazieren gehen", { exact: true })).toBeVisible();
    await expect(A.getByRole("button", { name: "Aufgabe anlegen" })).toHaveCount(0);
    await expect(A.getByRole("button", { name: "Als erledigt markieren" })).toHaveCount(0);

    await A.goto(`/workspaces/${workspaceId}/roadmaps`);
    await expect(A.getByText("Unser nächster gemeinsamer Abschnitt", { exact: true })).toBeVisible();
    await expect(A.getByRole("button", { name: "Schritt hinzufügen" })).toHaveCount(0);
    await A.goto(`/workspaces/${workspaceId}/reflections`);
    await expect(A.getByText("Ich wünsche mir mehr ruhige Zeit für unsere Gespräche.", { exact: true })).toBeVisible();
    await expect(A.getByRole("button", { name: "Kopie jetzt teilen" })).toHaveCount(0);
    await expect(A.getByRole("button", { name: "Geteilte Kopie entfernen" })).toHaveCount(0);

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
