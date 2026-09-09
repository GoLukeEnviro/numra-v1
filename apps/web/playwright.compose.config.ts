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
  // Scoped explicitly to system-journey.spec.ts: without this, any new spec added
  // under e2e-system/ (e.g. pr-web-00-visual-baseline.spec.ts) is silently picked
  // up too, front-loading extra tests onto this job's single worker before the one
  // real system-journey run -- discovered when that caused the real test to fail on
  // a tight expect timeout it otherwise passes (see PR-WEB-00).
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
  // recurring "element not found" failures on main's post-merge docker-compose-e2e
  // run). The overall 300_000ms budget above was already generous; this raises the
  // per-assertion budget to match, without touching test logic or retries.
  expect: { timeout: 15_000 },
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
