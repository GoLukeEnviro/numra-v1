import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const swSource = readFileSync(path.join(__dirname, "../../../../public/sw.js"), "utf-8");

/**
 * PWA-10 / #186: the offline behaviour is a deliberate product decision, not a defect.
 *
 * Measured on the audit stack: the service worker controls the page, but an offline
 * reload of a navigation fails (`offline_reload_ok: false`) because navigations are
 * handled network-only. The alternative — precaching an application shell with
 * server-rendered pages — was rejected: on a shared device a cached page could render
 * another person's data from cache, and this product's pages embed per-user profiles,
 * calculations and reports.
 *
 * The existing `sw.test.ts` already pins the /api/ bypass. These tests pin the second
 * half of the same decision, so a future "add offline support" change fails loudly and
 * has to argue with the ADR instead of silently weakening a privacy boundary.
 */
describe("public/sw.js navigation strategy (#186, ADR 014)", () => {
  const fetchHandler = swSource.slice(swSource.indexOf('addEventListener("fetch"'));

  it("caches only immutable static assets, declared by one allowlist predicate", () => {
    // The cacheable set must stay an explicit predicate, not an inlined set of
    // conditions sprinkled through the handler.
    expect(swSource).toMatch(/function isCacheableStaticAsset\(/);

    const predicate = swSource.slice(
      swSource.indexOf("function isCacheableStaticAsset("),
      swSource.indexOf("self.addEventListener(\"fetch\""),
    );
    // Only versioned build output, icons and the manifest are ever cacheable.
    expect(predicate).toContain('startsWith("/_next/static/")');
    expect(predicate).toContain('startsWith("/icons/")');
    expect(predicate).toContain('"/manifest.webmanifest"');
  });

  it("treats page navigations as network-only: no cache read on the success path", () => {
    // The navigation branch may only fall back to the cache in the *failure* path.
    // A `caches.match(req)` served before the network call is exactly the offline
    // shell this decision rejects.
    const navBranch = fetchHandler.slice(fetchHandler.lastIndexOf("event.respondWith"));
    expect(navBranch).toContain("fetch(req)");
    // The cache may appear only inside the rejection handler of the network fetch.
    const fallbackIndex = navBranch.indexOf("caches.match(req)");
    const catchIndex = navBranch.indexOf(".catch(");
    expect(catchIndex).toBeGreaterThan(-1);
    expect(fallbackIndex).toBeGreaterThan(catchIndex);
  });

  it("never writes a navigation response into the cache", () => {
    // There are exactly two cache-write kinds, both anchored to the static path: the
    // install-time `addAll` precache and the static branch's `cache.put(req, copy)`
    // where `copy` comes from serving a cacheable static asset. Neither may ever be
    // reached with a navigation response.
    const fetches = [...swSource.matchAll(/fetch\(req\)/g)].map((m) => m.index ?? 0);
    expect(fetches.length).toBeGreaterThan(0);

    // The navigation branch does not open a cache at all.
    const navBranch = fetchHandler.slice(fetchHandler.lastIndexOf("event.respondWith"));
    expect(navBranch).not.toContain("caches.open");

    // And no `cache.put` takes a response that came from the navigation fetch.
    expect(swSource).not.toMatch(/cache\.put\(req,\s*res\)/);
    expect(swSource).toMatch(/const copy = res\.clone\(\);/);
  });

  it("documents the shared-device reason in the source, where the next reader looks", () => {
    expect(swSource).toMatch(/privacy/i);
    expect(swSource.toLowerCase()).toMatch(/network-only|network only/);
  });
});
