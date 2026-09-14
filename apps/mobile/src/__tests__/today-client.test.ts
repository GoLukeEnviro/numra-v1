import { describe, expect, it, vi } from "vitest";

import { createTodayClient, todayIsoDate } from "../api/today-client";
import type { TokenStore } from "../api/auth-client";

function memoryStore(initial: string | null = "stored-token"): TokenStore & { value: string | null } {
  return {
    value: initial,
    async get() { return this.value; },
    async set(value) { this.value = value; },
    async delete() { this.value = null; },
  };
}

const person = { id: "p1", birth_first_names: "Lukas", preferred_name: null };

const timing = {
  personal_year: { display_value: "17/8" },
  personal_month: { display_value: "16/7" },
  personal_day: { display_value: "8" },
};

const brief = {
  person_id: "p1",
  as_of_date: "2026-08-19",
  knowledge_version: "1.0.0",
  sections: [
    { metric_id: "personal_year", display_name_de: "Persönliches Jahr", display_value: "17/8", text_de: "Text." },
  ],
};

function ok(body: unknown) {
  return { ok: true, status: 200, json: async () => body };
}

describe("todayIsoDate", () => {
  it("formats the local calendar day, never a UTC-shifted one", () => {
    expect(todayIsoDate(new Date(2026, 0, 3, 23, 30))).toBe("2026-01-03");
    expect(todayIsoDate(new Date(2026, 11, 31, 0, 15))).toBe("2026-12-31");
  });
});

describe("native today client", () => {
  it("sends the stored bearer token to every read endpoint", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(ok([person]))
      .mockResolvedValueOnce(ok(timing))
      .mockResolvedValueOnce(ok(brief));
    const client = createTodayClient("https://api.example.com", memoryStore(), fetcher);

    await expect(client.getFirstPerson()).resolves.toEqual(person);
    await expect(client.getTiming("p1", "2026-08-19")).resolves.toEqual(timing);
    await expect(client.getDailyBrief("p1", "2026-08-19")).resolves.toEqual(brief);

    expect(fetcher.mock.calls.map((call) => call[0])).toEqual([
      "https://api.example.com/v1/people",
      "https://api.example.com/v1/people/p1/timing?as_of_date=2026-08-19",
      "https://api.example.com/v1/people/p1/daily-brief?as_of_date=2026-08-19",
    ]);
    for (const call of fetcher.mock.calls) {
      expect(call[1].headers.Authorization).toBe("Bearer stored-token");
    }
  });

  it("reports no person instead of inventing one when the account is empty", async () => {
    const client = createTodayClient("https://api.example.com", memoryStore(), vi.fn().mockResolvedValue(ok([])));
    await expect(client.getFirstPerson()).resolves.toBeNull();
  });

  it("treats a missing credential as unauthorized without issuing a request", async () => {
    const fetcher = vi.fn();
    const client = createTodayClient("https://api.example.com", memoryStore(null), fetcher);
    await expect(client.getFirstPerson()).rejects.toThrow("UNAUTHORIZED");
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("surfaces a rejected credential as unauthorized so the caller can sign out", async () => {
    const store = memoryStore();
    const client = createTodayClient(
      "https://api.example.com",
      store,
      vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({}) }),
    );
    await expect(client.getTiming("p1", "2026-08-19")).rejects.toThrow("UNAUTHORIZED");
  });

  it("keeps transport failures distinct from authorization failures", async () => {
    const client = createTodayClient(
      "https://api.example.com",
      memoryStore(),
      vi.fn().mockResolvedValue({ ok: false, status: 503, json: async () => ({}) }),
    );
    await expect(client.getDailyBrief("p1", "2026-08-19")).rejects.toThrow("REQUEST_FAILED");
  });

  it("rejects payloads that do not carry the fields the screen renders", async () => {
    const timingClient = createTodayClient(
      "https://api.example.com",
      memoryStore(),
      vi.fn().mockResolvedValue(ok({ personal_year: { display_value: "17/8" } })),
    );
    await expect(timingClient.getTiming("p1", "2026-08-19")).rejects.toThrow("INVALID_TIMING_RESPONSE");

    const briefClient = createTodayClient(
      "https://api.example.com",
      memoryStore(),
      vi.fn().mockResolvedValue(ok({ ...brief, sections: [{ metric_id: "personal_year" }] })),
    );
    await expect(briefClient.getDailyBrief("p1", "2026-08-19")).rejects.toThrow("INVALID_DAILY_BRIEF_RESPONSE");

    const peopleClient = createTodayClient(
      "https://api.example.com",
      memoryStore(),
      vi.fn().mockResolvedValue(ok({ not: "a list" })),
    );
    await expect(peopleClient.getFirstPerson()).rejects.toThrow("INVALID_PEOPLE_RESPONSE");
  });
});
