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
});
