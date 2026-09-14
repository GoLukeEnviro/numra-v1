import { beforeEach, describe, expect, it, vi } from "vitest";

const secureStore = vi.hoisted(() => ({
  WHEN_UNLOCKED_THIS_DEVICE_ONLY: 1,
  getItemAsync: vi.fn(),
  setItemAsync: vi.fn(),
  deleteItemAsync: vi.fn(),
}));
vi.mock("expo-secure-store", () => secureStore);

import { secureTokenStore } from "../auth/secure-token-store";

describe("secureTokenStore", () => {
  beforeEach(() => vi.clearAllMocks());

  it("uses the non-synchronizing OS credential store", async () => {
    secureStore.getItemAsync.mockResolvedValue("token");
    await expect(secureTokenStore.get()).resolves.toBe("token");
    await secureTokenStore.set("new-token");
    expect(secureStore.setItemAsync).toHaveBeenCalledWith(
      "avenyth.native.session",
      "new-token",
      expect.objectContaining({ keychainAccessible: expect.any(Number) }),
    );
    await secureTokenStore.delete();
    expect(secureStore.deleteItemAsync).toHaveBeenCalledWith("avenyth.native.session");
  });
});
