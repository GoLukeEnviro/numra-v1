import { defineConfig, devices } from "@playwright/test";
import fs from "node:fs";

const localChromium = "/opt/pw-browsers/chromium";
const executablePath = fs.existsSync(localChromium) ? localChromium : undefined;

/**
 * REALITY_CHECK_2 Phase 2 -- the real two-account connections/consent/dual-profile/
 * relationship-type/dissolve journey (e2e-system/rc2-two-account-journey.spec.ts)
 * against an already-running, isolated `docker compose` stack brought up by
 * scripts/rc2-e2e.sh (project `numra-rc2`, web on host port 3100).
 *
 * Starts nothing itself (no webServer block) -- exactly like
 * playwright.compose.config.ts, whose baseURL rationale (`localhost`, not
 * `127.0.0.1`, so the real browser Origin matches CORS_ALLOWED_ORIGINS) applies
 * here too; docker-compose.rc2.yml sets that allowlist to the 3100 origin.
 *
 * Two projects, one per required viewport. The spec still creates its own two
 * `browser.newContext({ viewport, isMobile, hasTouch })` (users A and B) and
 * asserts the measured innerWidth/innerHeight before any product check -- the
 * project only carries the target size via `metadata` and selects which viewport
 * this run exercises.
 */
const port = Number(process.env.COMPOSE_WEB_PORT || 3100);
// The stack under test: the local numra-rc2 compose stack by default. Point
// RC2_BASE_URL at a remote instance (e.g. the numra-audit stack on
// HermesTrader) to run this exact suite as an automated acceptance pass
// against it -- accounts are self-registered per run, so no manual login or
// stored credential is ever involved.
const baseURL = process.env.RC2_BASE_URL || `http://localhost:${port}`;

const DESKTOP = { width: 1440, height: 900 };
const MOBILE = { width: 390, height: 844 };

export default defineConfig({
  testDir: "./e2e-system",
  testMatch: "rc2-two-account-journey.spec.ts",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  timeout: 300_000,
  expect: { timeout: 15_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    ...(executablePath ? { launchOptions: { executablePath } } : {}),
  },
  projects: [
    {
      name: "desktop-1440x900",
      metadata: { viewport: DESKTOP, isMobile: false, hasTouch: false },
      use: { ...devices["Desktop Chrome"], viewport: DESKTOP },
    },
    {
      name: "mobile-390x844",
      metadata: { viewport: MOBILE, isMobile: true, hasTouch: true },
      use: {
        ...devices["Pixel 7"],
        viewport: MOBILE,
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
});
