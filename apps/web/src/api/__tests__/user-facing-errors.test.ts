import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "@/api/client";

describe("user-facing API error messages", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("replaces the English server text of BETA_ACCESS_REQUIRED with an understandable German one", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({ code: "BETA_ACCESS_REQUIRED", message: "beta access required for report" }),
          { status: 403, headers: { "content-type": "application/json" } },
        ),
      ),
    );

    const error = await api.auth.me().catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("BETA_ACCESS_REQUIRED");
    expect((error as ApiError).status).toBe(403);
    expect((error as ApiError).message).toMatch(/freigeschaltete Beta-Konten/);
    expect((error as ApiError).message).not.toMatch(/beta access required/);
  });

  it("names the wait for QUOTA_EXCEEDED from retry_after_seconds", async () => {
    const respond = (seconds: number) =>
      vi.stubGlobal(
        "fetch",
        vi.fn(async () =>
          new Response(
            JSON.stringify({ code: "QUOTA_EXCEEDED", message: "quota exceeded for report", retry_after_seconds: seconds }),
            { status: 429, headers: { "content-type": "application/json" } },
          ),
        ),
      );

    respond(30);
    expect(((await api.auth.me().catch((e: unknown) => e)) as ApiError).message).toMatch(/etwa einer Minute/);
    respond(1500);
    const error = (await api.auth.me().catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe("QUOTA_EXCEEDED");
    expect(error.status).toBe(429);
    expect(error.message).toMatch(/Nutzungslimit/);
    expect(error.message).toMatch(/25 Minuten/);
    respond(7200);
    expect(((await api.auth.me().catch((e: unknown) => e)) as ApiError).message).toMatch(/2 Stunden/);
  });
});
