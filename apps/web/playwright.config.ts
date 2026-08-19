import { defineConfig, devices } from "@playwright/test";
import fs from "node:fs";

const localChromium = "/opt/pw-browsers/chromium";
const executablePath = fs.existsSync(localChromium) ? localChromium : undefined;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:4173",
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
    // API_INTERNAL_URL is a runtime (server-only) env var read at `next start`, not a
    // NEXT_PUBLIC_ build-time one — the build step itself needs no API-related env at
    // all now (see next.config.mjs's rewrites()). Requests the browser makes to
    // same-origin /api/* are proxied to whatever API_INTERNAL_URL says; when a test
    // uses page.route() to intercept those instead (see golden-journey.spec.ts), the
    // proxy target is never actually reached.
    command: "pnpm build && API_INTERNAL_URL=http://127.0.0.1:4173 npx next start -p 4173",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
