import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const swSource = readFileSync(path.join(__dirname, "../../../../public/sw.js"), "utf-8");

/**
 * V1.5 Epic I hard failure condition: the service worker must never cache a
 * response from /api/* (Numra's same-origin backend proxy, which carries
 * session-authenticated personal data). This is a static-source guard, not a
 * runtime ServiceWorker test -- jsdom has no ServiceWorker/caches API -- but it
 * fails loudly if the /api/ bypass or the precache allowlist ever regresses.
 */
describe("public/sw.js", () => {
  it("bypasses (returns early, no interception) for any request under /api/", () => {
    expect(swSource).toMatch(/url\.pathname\.startsWith\(["']\/api\/["']\)/);
    // The bypass must be a `return;` inside the fetch handler, before any
    // `event.respondWith` call that could serve a cached response.
    const fetchHandler = swSource.slice(swSource.indexOf('addEventListener("fetch"'));
    const bypassIndex = fetchHandler.indexOf("/api/");
    const firstRespondWith = fetchHandler.indexOf("event.respondWith");
    expect(bypassIndex).toBeGreaterThan(-1);
    expect(bypassIndex).toBeLessThan(firstRespondWith);
  });

  it("never precaches anything under /api/", () => {
    const match = swSource.match(/PRECACHE_URLS\s*=\s*(\[[^\]]*\]);/);
    expect(match).not.toBeNull();
    const urls = JSON.parse(match![1].replace(/'/g, '"')) as string[];
    expect(urls.length).toBeGreaterThan(0);
    for (const url of urls) {
      expect(url.startsWith("/api/")).toBe(false);
    }
  });
});
