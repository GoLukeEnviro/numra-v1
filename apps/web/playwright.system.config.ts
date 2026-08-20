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
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  timeout: 120_000,
  reporter: [["list"]],
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
