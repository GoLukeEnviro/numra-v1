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
    // Build with the API base pointed at this same origin so the fully-mocked
    // journey below (page.route) never has to deal with cross-origin/CORS
    // preflight semantics — there is no live backend in this sandbox to test
    // against (see apps/web/e2e/golden-journey.spec.ts for the real contract
    // this exercises via route interception). NEXT_PUBLIC_* vars are inlined
    // at build time, so both the build and the start need it set.
    command:
      "NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:4173 pnpm build && NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:4173 npx next start -p 4173",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
