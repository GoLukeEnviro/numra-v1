import { describe, expect, it, vi } from "vitest";

import { createAuthClient, type TokenStore } from "../api/auth-client";

function memoryStore(initial: string | null = null): TokenStore & { value: string | null } {
  return {
    value: initial,
    async get() { return this.value; },
    async set(value) { this.value = value; },
    async delete() { this.value = null; },
  };
}

const user = { id: "u1", email: "mobile@example.com", role: "USER", is_active: true };

describe("native auth client", () => {
  it("stores the opaque token after login without retaining the password", async () => {
    const store = memoryStore();
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ access_token: "secret-token", token_type: "Bearer", expires_at: "2099-01-01T00:00:00Z", user }),
    });
    const client = createAuthClient("https://api.example.com", store, fetcher);

    await expect(client.login("mobile@example.com", "not-stored")).resolves.toEqual(user);
    expect(store.value).toBe("secret-token");
    expect(JSON.stringify(store)).not.toContain("not-stored");
  });

  it("restores a stored session and clears a rejected credential", async () => {
    const store = memoryStore("stored-token");
    const fetcher = vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({}) });
    const client = createAuthClient("https://api.example.com", store, fetcher);
    await expect(client.restore()).resolves.toBeNull();
    expect(store.value).toBeNull();
  });

  it("removes the local credential even when remote logout is unavailable", async () => {
    const store = memoryStore("stored-token");
    const client = createAuthClient(
      "https://api.example.com",
      store,
      vi.fn().mockRejectedValue(new Error("offline")),
    );
    await expect(client.logout()).rejects.toThrow("offline");
    expect(store.value).toBeNull();
  });
});
