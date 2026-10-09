import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, TimeoutError } from "@/api/client";

/**
 * A3/A5 follow-up: the fetch wrapper must turn a hung connection into a visible,
 * typed error instead of a spinner that never resolves. Verified against a
 * representative long-running call (a Copilot reply) rather than every call site --
 * the mechanism lives once in `request()`.
 */
describe("api client request timeout", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("aborts and rejects with TimeoutError once the deadline elapses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init?: RequestInit) => {
        return new Promise((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => {
            const abortError = new Error("aborted");
            abortError.name = "AbortError";
            reject(abortError);
          });
        });
      }),
    );

    const pending = api.me.copilot.threads.messages.post("thread-1", { content: "hi" });
    const assertion = expect(pending).rejects.toBeInstanceOf(TimeoutError);

    await vi.advanceTimersByTimeAsync(150_000);
    await assertion;
  });

  it("resolves normally when the response arrives well within the deadline", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Response(JSON.stringify({ ok: true }), {
            status: 200,
            headers: { "content-type": "application/json" },
          }),
      ),
    );

    await expect(
      api.me.copilot.threads.messages.post("thread-1", { content: "hi" }),
    ).resolves.toEqual({ ok: true });
  });
});
