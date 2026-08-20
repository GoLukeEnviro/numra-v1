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
 *
 * baseURL deliberately uses `localhost`, not `127.0.0.1`: numra_api's
 * OriginValidationMiddleware allows a request with no Origin header at all (how
 * page.request.post reaches the API for registration) but rejects a real browser's
 * Origin on a state-changing request unless it's in cors_allowed_origins -- whose
 * default already includes exactly `http://localhost:3000` (config.py), matching
 * docker-compose.yml's real web port. `127.0.0.1:3000` is not in that default list
 * and docker-compose.yml has no override for it, so using `127.0.0.1` here would
 * make the real browser's login/register-form submissions fail Origin validation
 * against the actual compose stack -- a real deployment visited at
 * `http://localhost:3000` (the compose default) hits none of this.
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
    baseURL: `http://localhost:${port}`,
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
