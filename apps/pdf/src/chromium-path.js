/**
 * Resolves Playwright launch options for Chromium.
 *
 * Priority: an explicit `PLAYWRIGHT_CHROMIUM_PATH` env var always wins. Otherwise, if
 * the sandbox/dev-environment's known pre-installed stable path exists on disk, use
 * it. Otherwise leave `executablePath` unset so Playwright resolves its own
 * normally-installed (via `playwright install`) browser — the correct behavior in CI
 * and in the Docker image, neither of which has this sandbox-specific path.
 */

const SANDBOX_CHROMIUM_PATH = "/opt/pw-browsers/chromium";

export function resolveLaunchOptions(existsSyncFn) {
  const explicit = process.env.PLAYWRIGHT_CHROMIUM_PATH;
  if (explicit) {
    return { headless: true, executablePath: explicit };
  }
  if (existsSyncFn(SANDBOX_CHROMIUM_PATH)) {
    return { headless: true, executablePath: SANDBOX_CHROMIUM_PATH };
  }
  return { headless: true };
}
