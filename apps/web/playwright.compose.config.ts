import { defineConfig, devices } from "@playwright/test";
import fs from "node:fs";

const localChromium = "/opt/pw-browsers/chromium";
const executablePath = fs.existsSync(localChromium) ? localChromium : undefined;

/**
 * Config for the real system journey (e2e-system/system-journey.spec.ts) run against
 * an already-running `docker compose up` stack -- the actual container topology
 * (docker-compose.yml), not a manually-started Next.js/FastAPI process pair. Unlike
 * playwright.system.config.ts (which owns starting its own Next.js server pointed at
 * a manually-started API), this config starts nothing: docker compose's `web` service
 * is already listening on COMPOSE_WEB_PORT (default 3000, matching docker-compose.yml)
 * by the time this runs. See specs/evidence/final-release-closure.md for the full
 * Gate C sequence this belongs to.
 */
const port = Number(process.env.COMPOSE_WEB_PORT || 3000);

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
  // No webServer block: docker compose already owns and starts the web container.
});
