/**
 * Same-origin API guard for the RC2 two-account journey.
 *
 * Invariant: the browser may only reach the application API through same-origin
 * requests under `/api/*` (the Next.js route handler at `src/app/api/[...path]`
 * proxies them server-side to `API_INTERNAL_URL`). Any browser request that talks
 * to the API's own origin directly is a contract violation — it would mean the
 * built image stopped being environment-portable and the browser learned the real
 * backend origin.
 *
 * The predicate is deliberately semantic: it compares the request's origin with
 * the page's own origin and only classifies API-shaped paths. It must never
 * depend on one hardcoded port — the RC2 stack remaps the API port per
 * environment (`docker-compose.rc2.yml`), and a hardcoded port silently stops
 * matching the moment that mapping changes.
 */

/** Path prefixes that identify application-API traffic (never a static asset). */
const API_PATH_PREFIXES = ["/api", "/v1"];

/**
 * Hostnames that can only ever mean "the API container itself" and are never a
 * legitimate browser target. `api` is the compose service DNS name: it resolves
 * inside the compose network but has no meaning in a browser context, so seeing
 * it from a page is always a violation regardless of path.
 */
const INTERNAL_API_HOSTS = new Set(["api"]);

/**
 * True when `requestUrl` must be reported as an off-origin API call: the request
 * leaves the page's own origin AND either targets an API-shaped path or the
 * internal API host.
 *
 * Relative URLs are resolved against `pageOrigin`, so callers can pass whatever
 * shape they hold (absolute request URL, redirect target, or a relative path).
 * Non-API cross-origin resources (fonts, CDNs) return false.
 */
export function isOffOriginApiRequest(requestUrl: string, pageOrigin: string): boolean {
  let url: URL;
  try {
    url = new URL(requestUrl, pageOrigin);
  } catch {
    return false;
  }

  if (url.origin === new URL(pageOrigin).origin) return false;
  if (INTERNAL_API_HOSTS.has(url.hostname)) return true;
  return API_PATH_PREFIXES.some(
    (prefix) => url.pathname === prefix || url.pathname.startsWith(`${prefix}/`),
  );
}
