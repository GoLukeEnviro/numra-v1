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

// Docker's default /dev/shm is 64MB; Chromium's own renderer process routinely wants
// more than that for real page content, and without this flag it doesn't fail fast --
// it hangs or crash-loops silently, which is indistinguishable from "just slow" from
// the outside (confirmed via a real docker-compose-e2e run: raising every timeout on
// both the client and server side up to 150s changed nothing, because the render was
// never going to complete at all, not merely running past whatever bound was set).
// Harmless outside a container (falls back to /tmp instead of shared memory).
const DOCKER_SAFE_ARGS = ["--disable-dev-shm-usage"];

export function resolveLaunchOptions(existsSyncFn) {
  const explicit = process.env.PLAYWRIGHT_CHROMIUM_PATH;
  if (explicit) {
    return { headless: true, executablePath: explicit, args: DOCKER_SAFE_ARGS };
  }
  if (existsSyncFn(SANDBOX_CHROMIUM_PATH)) {
    return { headless: true, executablePath: SANDBOX_CHROMIUM_PATH, args: DOCKER_SAFE_ARGS };
  }
  return { headless: true, args: DOCKER_SAFE_ARGS };
}
