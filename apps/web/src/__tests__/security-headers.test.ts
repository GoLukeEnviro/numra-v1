import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";

import { middleware } from "../middleware";

/**
 * Security-header contract for the web surface.
 *
 * The headers are set on two surfaces -- the per-request middleware (CSP with a
 * fresh nonce, cache policy, HSTS) and the static `headers()` block in
 * next.config.mjs (the framing/sniffing/referrer/permissions family, plus HSTS
 * for the paths the middleware matcher excludes). This spec pins BOTH, by name
 * and value, because they were previously untested: that is exactly how a real
 * gap -- no HSTS on any response -- shipped unnoticed.
 *
 * A regression here (a dropped or weakened header) must fail the suite.
 */

interface HeaderRule {
  source: string;
  headers: { key: string; value: string }[];
}

function runMiddleware(pathname = "/login") {
  const request = new NextRequest(new URL(`http://localhost:3000${pathname}`));
  return middleware(request);
}

/** Lowercased header lookup for a real Response. */
function headerMap(response: Response): Record<string, string> {
  const map: Record<string, string> = {};
  response.headers.forEach((value, key) => {
    map[key.toLowerCase()] = value;
  });
  return map;
}

/** The static header list next.config.mjs applies to non-API routes.
 *
 * Read as text and evaluated rather than imported: `next.config.mjs` has no
 * declaration file, so any import form fails `tsc --noEmit` under `strict`. The
 * module is a 30-line config object with no side effects, so evaluating it here
 * is safe and keeps the assertion on the REAL shipped config (not a copy).
 */
async function configuredHeaders(): Promise<Record<string, string>> {
  const { readFileSync } = await import("node:fs");
  const { join } = await import("node:path");
  const configPath = join(__dirname, "..", "..", "next.config.mjs");
  const source = readFileSync(configPath, "utf8");
  const asModule = source.replace("export default nextConfig;", "return nextConfig;");
  const load = new Function(asModule) as () => { headers?: () => Promise<HeaderRule[]> };
  const headersFn = load().headers;

  expect(headersFn, "next.config.mjs must define a headers() function").toBeDefined();
  const rules = await headersFn!();
  const pageRule = rules.find((rule) => rule.source.includes("api"));
  expect(pageRule, "a header rule for non-API routes must exist").toBeDefined();
  const map: Record<string, string> = {};
  for (const header of pageRule!.headers) {
    map[header.key.toLowerCase()] = header.value;
  }
  return map;
}

describe("web security headers: middleware surface", () => {
  it("sends Strict-Transport-Security so a browser cannot stay on plaintext", () => {
    const headers = headerMap(runMiddleware());
    expect(headers["strict-transport-security"]).toBeDefined();
    expect(headers["strict-transport-security"]).toMatch(/max-age=\d{6,}/);
  });

  it("keeps the CSP strong: fresh nonce per response, strict-dynamic, locked defaults", () => {
    const first = headerMap(runMiddleware())["content-security-policy"] ?? "";
    const second = headerMap(runMiddleware())["content-security-policy"] ?? "";

    expect(first).toContain("default-src 'self'");
    expect(first).toContain("'strict-dynamic'");
    expect(first).toContain("object-src 'none'");
    expect(first).toContain("base-uri 'self'");
    expect(first).toContain("form-action 'self'");
    expect(first).toContain("frame-ancestors 'none'");
    expect(first).toContain("connect-src 'self'");

    const firstNonce = first.match(/'nonce-([^']+)'/)?.[1];
    const secondNonce = second.match(/'nonce-([^']+)'/)?.[1];
    expect(firstNonce).toBeTruthy();
    expect(secondNonce).toBeTruthy();
    expect(firstNonce).not.toBe(secondNonce);
  });

  it("never allows unsafe-eval outside development", () => {
    // vitest runs with NODE_ENV=test, so this asserts the non-development branch.
    expect(process.env.NODE_ENV).not.toBe("development");
    expect(headerMap(runMiddleware())["content-security-policy"]).not.toContain("'unsafe-eval'");
  });

  it("keeps private pages out of shared caches", () => {
    expect(headerMap(runMiddleware())["cache-control"]).toBe("private, no-store");
  });
});

describe("web security headers: next.config.mjs surface", () => {
  it("applies the framing/sniffing/referrer/permissions family", async () => {
    const headers = await configuredHeaders();
    expect(headers["x-content-type-options"]).toBe("nosniff");
    expect(headers["x-frame-options"]).toBe("DENY");
    expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin");
    expect(headers["permissions-policy"]).toContain("geolocation=()");
    expect(headers["permissions-policy"]).toContain("camera=()");
    expect(headers["permissions-policy"]).toContain("microphone=()");
    expect(headers["permissions-policy"]).toContain("payment=()");
  });

  it("sends Strict-Transport-Security here too, so the API-excluded paths get it", async () => {
    const headers = await configuredHeaders();
    expect(headers["strict-transport-security"]).toBeDefined();
    expect(headers["strict-transport-security"]).toMatch(/max-age=\d{6,}/);
  });
});
