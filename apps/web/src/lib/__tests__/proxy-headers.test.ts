// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  buildUpstreamHeaders,
  readProxyConfig,
  resolveClientIp,
} from "@/lib/proxy-headers";
import { GET, POST } from "@/app/api/[...path]/route";
import { NextRequest } from "next/server";

const SECRET = "s".repeat(40);

function incoming(init: Record<string, string>): Headers {
  return new Headers(init);
}

describe("buildUpstreamHeaders", () => {
  it("strips client-supplied X-Numra-*, X-Forwarded-* and identity headers", () => {
    const upstream = buildUpstreamHeaders(
      incoming({
        "x-numra-proxy-auth": "forged",
        "x-numra-anything": "1",
        "x-forwarded-for": "6.6.6.6",
        "x-forwarded-host": "evil.example",
        "x-real-ip": "6.6.6.6",
        forwarded: "for=6.6.6.6",
        "cf-connecting-ip": "6.6.6.6",
        "true-client-ip": "6.6.6.6",
        "x-user-id": "admin",
        cookie: "numra_session=abc",
        "x-csrf-token": "t",
        origin: "https://app.example",
        host: "internal",
      }),
      { secret: undefined, trustedHops: 0 },
    );
    const names = [...upstream.keys()].sort();
    expect(names).toEqual(["cookie", "origin", "x-csrf-token"]);
  });

  it("sets its own secret and the proxy-appended client IP, never the client's", () => {
    const upstream = buildUpstreamHeaders(
      incoming({
        "x-numra-proxy-auth": "forged",
        "x-forwarded-for": "6.6.6.6, 203.0.113.9",
      }),
      { secret: SECRET, trustedHops: 1 },
    );
    expect(upstream.get("x-numra-proxy-auth")).toBe(SECRET);
    expect(upstream.get("x-forwarded-for")).toBe("203.0.113.9");
  });

  it("sends the secret but no client IP when no trusted hop is configured", () => {
    const upstream = buildUpstreamHeaders(incoming({ "x-forwarded-for": "6.6.6.6" }), {
      secret: SECRET,
      trustedHops: 0,
    });
    expect(upstream.get("x-numra-proxy-auth")).toBe(SECRET);
    expect(upstream.has("x-forwarded-for")).toBe(false);
  });

  it("sends nothing proxy-related when no secret is configured", () => {
    const upstream = buildUpstreamHeaders(
      incoming({ "x-forwarded-for": "203.0.113.9" }),
      { secret: undefined, trustedHops: 1 },
    );
    expect(upstream.has("x-numra-proxy-auth")).toBe(false);
    expect(upstream.has("x-forwarded-for")).toBe(false);
  });
});

describe("resolveClientIp", () => {
  it("takes the Nth entry from the right and rejects non-IP values", () => {
    expect(resolveClientIp(incoming({ "x-forwarded-for": "1.1.1.1, 2.2.2.2, 3.3.3.3" }), 2)).toBe(
      "2.2.2.2",
    );
    expect(resolveClientIp(incoming({ "x-forwarded-for": "1.1.1.1" }), 2)).toBeUndefined();
    expect(resolveClientIp(incoming({ "x-forwarded-for": "not-an-ip" }), 1)).toBeUndefined();
    expect(resolveClientIp(incoming({}), 1)).toBeUndefined();
    expect(resolveClientIp(incoming({ "x-forwarded-for": "1.1.1.1" }), 0)).toBeUndefined();
  });
});

describe("readProxyConfig", () => {
  it("defaults to off and ignores invalid hop counts", () => {
    expect(readProxyConfig({} as NodeJS.ProcessEnv)).toEqual({ secret: undefined, trustedHops: 0 });
    expect(
      readProxyConfig({ INTERNAL_PROXY_SHARED_SECRET: SECRET, TRUSTED_PROXY_HOPS: "x" } as never),
    ).toEqual({ secret: SECRET, trustedHops: 0 });
    expect(readProxyConfig({ TRUSTED_PROXY_HOPS: "2" } as never).trustedHops).toBe(2);
  });

  it("rejects a short or whitespace-padded secret loudly, without echoing it", () => {
    for (const bad of ["short", `${SECRET} `, `	${SECRET}`]) {
      let message = "";
      try {
        readProxyConfig({ INTERNAL_PROXY_SHARED_SECRET: bad } as never);
      } catch (error) {
        message = (error as Error).message;
      }
      expect(message).toContain("at least 32");
      expect(message).not.toContain(bad.trim() || "x");
    }
  });
});

describe("API proxy route handler", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  async function call(handler: typeof GET, headers: Record<string, string>, method = "GET") {
    const fetchMock = vi.fn(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubEnv("API_INTERNAL_URL", "http://api.internal:8000");
    const request = new NextRequest("http://web.test/api/v1/auth/login", { method, headers });
    await handler(request, { params: Promise.resolve({ path: ["v1", "auth", "login"] }) });
    const [, init] = fetchMock.mock.calls[0] as unknown as [URL, RequestInit];
    return new Headers(init.headers);
  }

  it("forwards the secret and trusted IP and drops forged headers", async () => {
    vi.stubEnv("INTERNAL_PROXY_SHARED_SECRET", SECRET);
    vi.stubEnv("TRUSTED_PROXY_HOPS", "1");
    const sent = await call(GET, {
      "x-forwarded-for": "6.6.6.6, 203.0.113.9",
      "x-numra-proxy-auth": "forged",
      "x-user-id": "admin",
      cookie: "numra_session=abc",
    });
    expect(sent.get("x-numra-proxy-auth")).toBe(SECRET);
    expect(sent.get("x-forwarded-for")).toBe("203.0.113.9");
    expect(sent.has("x-user-id")).toBe(false);
    expect(sent.get("cookie")).toBe("numra_session=abc");
  });

  it("never echoes the secret back to the browser", async () => {
    vi.stubEnv("INTERNAL_PROXY_SHARED_SECRET", SECRET);
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 200 })));
    const request = new NextRequest("http://web.test/api/v1/x", { method: "POST", body: "{}" });
    const response = await POST(request, { params: Promise.resolve({ path: ["v1", "x"] }) });
    expect(JSON.stringify([...response.headers.entries()])).not.toContain(SECRET);
    expect(await response.text()).not.toContain(SECRET);
  });
});
