import { describe, expect, it, vi } from "vitest";

import { loadPublicConfig, resolveApiOrigin } from "../api/public-config";

describe("resolveApiOrigin", () => {
  it("rejects a missing API origin", () => {
    expect(() => resolveApiOrigin(undefined)).toThrow("EXPO_PUBLIC_API_URL");
  });

  it("requires HTTPS for non-local services", () => {
    expect(() => resolveApiOrigin("http://api.example.com/")).toThrow("HTTPS");
  });

  it("allows local HTTP and removes the trailing slash", () => {
    expect(resolveApiOrigin("http://localhost:8000/")).toBe("http://localhost:8000");
  });
});

describe("loadPublicConfig", () => {
  it("loads and validates the existing public configuration endpoint", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ brand_name: "AVENYTH", allow_self_signup: true }),
    });

    await expect(loadPublicConfig("https://api.example.com", fetcher)).resolves.toEqual({
      brandName: "AVENYTH",
      allowSelfSignup: true,
    });
    expect(fetcher).toHaveBeenCalledWith("https://api.example.com/v1/config/public", {
      headers: { Accept: "application/json" },
    });
  });

  it("rejects unsuccessful and malformed responses", async () => {
    const unavailable = vi.fn().mockResolvedValue({ ok: false, status: 503 });
    await expect(loadPublicConfig("https://api.example.com", unavailable)).rejects.toThrow(
      "503",
    );

    const malformed = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ brand_name: "" }),
    });
    await expect(loadPublicConfig("https://api.example.com", malformed)).rejects.toThrow(
      "invalid public configuration",
    );
  });
});
