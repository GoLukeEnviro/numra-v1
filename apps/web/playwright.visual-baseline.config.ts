import { defineConfig, devices } from "@playwright/test";
import fs from "node:fs";

const localChromium = "/opt/pw-browsers/chromium";
const executablePath = fs.existsSync(localChromium) ? localChromium : undefined;

/**
 * Config for pr-web-00-visual-baseline.spec.ts only (screenshot generator for the
 * human reality-check, PR-WEB-00). Deliberately separate from both
 * playwright.config.ts (golden-journey.spec.ts) and playwright.system.config.ts
 * (system-journey.spec.ts, which needs a real FastAPI/Postgres/worker stack): this
 * one mocks the backend with page.route() exactly like golden-journey.spec.ts.
 *
 * Same `next build && next start` pattern as playwright.config.ts (NOT `next dev`:
 * dev mode's HMR runtime evaluates strings as JS for React Refresh, which
 * next.config.mjs's CSP -- `script-src 'self' 'unsafe-inline'`, deliberately no
 * `unsafe-eval` -- blocks outright, breaking hydration before AuthProvider's
 * useEffect ever fires; verified locally, see PR-WEB-00's final report).
 */
export default defineConfig({
  testDir: "./e2e-system",
  testMatch: "pr-web-00-visual-baseline.spec.ts",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  timeout: 60_000,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:4181",
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
    // No API_INTERNAL_URL: every request this spec makes is mocked with
    // page.route() before it leaves the browser, so the server-side proxy target
    // is never actually reached (same reasoning as playwright.config.ts's comment).
    // Left unset rather than cross-shell `VAR=value cmd` syntax, which cmd.exe
    // (this sandbox's default shell for spawned processes) doesn't support.
    command: "pnpm build && npx next start -p 4181",
    url: "http://127.0.0.1:4181",
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
