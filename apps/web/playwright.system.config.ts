import { defineConfig, devices } from "@playwright/test";
import fs from "node:fs";

const localChromium = "/opt/pw-browsers/chromium";
const executablePath = fs.existsSync(localChromium) ? localChromium : undefined;

/**
 * Config for the REAL, non-mocked system E2E test (system-journey.spec.ts).
 *
 * Unlike playwright.config.ts (golden-journey.spec.ts, which intercepts every API
 * call with page.route() and never reaches a real backend), this starts the Next.js
 * server pointed at API_INTERNAL_SYSTEM_URL — a real FastAPI instance, backed by a
 * real Postgres database, a real report worker, and the real internal PDF service —
 * that the caller is responsible for having already started (see
 * specs/evidence/system-e2e.md for the exact startup sequence). Nothing in this test
 * suite starts Postgres/Redis/the API/the worker/the PDF service itself; it only
 * starts the one process it actually owns (the Next.js server) and drives the browser
 * against the real stack behind it.
 */
const apiInternalUrl = process.env.API_INTERNAL_SYSTEM_URL || "http://127.0.0.1:8010";
const port = Number(process.env.SYSTEM_E2E_WEB_PORT || 4180);

export default defineConfig({
  testDir: "./e2e-system",
  // Scoped explicitly to system-journey.spec.ts -- see playwright.compose.config.ts
  // for why: without this, any new spec added under e2e-system/ is silently picked
  // up too, front-loading extra tests onto this job's single worker.
  testMatch: "system-journey.spec.ts",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  // The spec's own test.setTimeout(300_000) takes precedence for that test; this
  // config-level default is kept in step so it's never the tighter of the two.
  timeout: 300_000,
  // Playwright's built-in default expect() timeout (5_000ms) is too tight for
  // individual assertions in this long, single-worker journey against a real,
  // freshly-booted stack under CI load -- observed causing sporadic failures at
  // arbitrary, different steps of the same test across unrelated commits (see
  // recurring "element not found" failures on main's post-merge system-e2e run).
  // The overall 300_000ms budget above was already generous; this raises the
  // per-assertion budget to match, without touching test logic or retries.
  expect: { timeout: 15_000 },
  // list for live CI console output; html (never auto-opened) as an uploadable
  // failure artifact -- the system-e2e job archives playwright-report/ and
  // test-results/ (traces) whenever this job fails.
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        ...(executablePath ? { launchOptions: { executablePath } } : {}),
      },
    },
  ],
  webServer: {
    command: `pnpm build && API_INTERNAL_URL=${apiInternalUrl} npx next start -p ${port}`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: false,
    timeout: 180_000,
  },
});
