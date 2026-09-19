import { describe, expect, it } from "vitest";

import { isOffOriginApiRequest } from "@/lib/off-origin-guard";

/**
 * The RC2 journey's off-origin guard exists to catch one regression class: the
 * browser talking to the API's own origin instead of the same-origin `/api/*`
 * proxy. These cases pin the predicate's contract. The RC2 stack publishes the
 * API on a remapped host port (58080 locally via docker-compose.rc2.yml); a guard
 * that hardcodes a different port is blind to exactly the traffic it exists to
 * catch, so the remapped-port case below is the load-bearing one.
 */

const PAGE_ORIGIN = "http://localhost:3100";

describe("isOffOriginApiRequest", () => {
  it("allows the same-origin /api/* proxy path the app is supposed to use", () => {
    expect(isOffOriginApiRequest("http://localhost:3100/api/v1/health/live", PAGE_ORIGIN)).toBe(
      false,
    );
    expect(
      isOffOriginApiRequest("http://localhost:3100/api/v1/workspaces?limit=10", PAGE_ORIGIN),
    ).toBe(false);
  });

  it("allows cross-origin non-API resources (fonts, CDNs) instead of false-flagging them", () => {
    expect(isOffOriginApiRequest("https://fonts.gstatic.com/s/inter.woff2", PAGE_ORIGIN)).toBe(
      false,
    );
    expect(isOffOriginApiRequest("https://cdn.example.com/analytics.js", PAGE_ORIGIN)).toBe(false);
  });

  it("flags a direct call to the remapped RC2 API port", () => {
    expect(isOffOriginApiRequest("http://localhost:58080/v1/health/live", PAGE_ORIGIN)).toBe(true);
  });

  it("flags a direct call to the API's default port", () => {
    expect(isOffOriginApiRequest("http://127.0.0.1:8000/v1/health/live", PAGE_ORIGIN)).toBe(true);
  });

  it("flags a direct call to the compose service hostname", () => {
    expect(isOffOriginApiRequest("http://api:8000/v1/health/live", PAGE_ORIGIN)).toBe(true);
  });

  it("flags the same direct-API call when the page runs on a remote audit origin", () => {
    const remoteOrigin = "https://agent0-1.taile6801f.ts.net:8444";
    expect(isOffOriginApiRequest(`${remoteOrigin}/api/v1/health/live`, remoteOrigin)).toBe(false);
    expect(isOffOriginApiRequest("http://localhost:58080/v1/health/live", remoteOrigin)).toBe(true);
  });

  it("keeps working for relative paths and query strings", () => {
    expect(isOffOriginApiRequest("/api/v1/health/live", PAGE_ORIGIN)).toBe(false);
    expect(isOffOriginApiRequest("/v1/health/live", "http://localhost:58080")).toBe(false);
    expect(isOffOriginApiRequest("http://api:8000/v1/health/live?probe=1", PAGE_ORIGIN)).toBe(true);
  });
});
