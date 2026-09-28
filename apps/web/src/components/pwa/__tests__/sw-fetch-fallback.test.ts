import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const swSource = readFileSync(path.join(__dirname, "../../../../public/sw.js"), "utf-8");

type FetchHandler = (event: { request: Request; respondWith: (r: Promise<Response>) => void }) => void;

/**
 * #212: with the network down and nothing cached, the fetch handler used to resolve
 * respondWith() with `undefined`, which the browser reports as
 * "TypeError: Failed to convert value to 'Response'". jsdom has no ServiceWorker
 * runtime, so this evaluates sw.js against minimal fakes of `self`, `caches` and
 * `fetch` and drives the real fetch listener.
 */
function loadFetchHandler(fakeFetch: () => Promise<Response>): FetchHandler {
  const listeners: Record<string, FetchHandler> = {};
  const self = {
    location: { origin: "https://avenyth.de" },
    addEventListener: (type: string, fn: FetchHandler) => {
      listeners[type] = fn;
    },
  };
  const caches = {
    match: async () => undefined,
    open: async () => ({ put: async () => undefined }),
  };
  new Function("self", "caches", "fetch", "Response", swSource)(self, caches, fakeFetch, Response);
  const handler = listeners.fetch;
  if (!handler) throw new Error("sw.js registered no fetch listener");
  return handler;
}

async function respond(url: string, fakeFetch: () => Promise<Response>): Promise<Response> {
  let result: Promise<Response> | undefined;
  loadFetchHandler(fakeFetch)({
    request: new Request(url),
    respondWith: (r) => {
      result = r;
    },
  });
  if (!result) throw new Error("fetch handler did not call respondWith");
  return result;
}

const offline = () => Promise.reject(new TypeError("Failed to fetch"));

describe("public/sw.js offline fallback (#212)", () => {
  it("answers an uncached navigation with a network error, never undefined", async () => {
    const res = await respond("https://avenyth.de/health_check.json", offline);
    expect(res).toBeInstanceOf(Response);
    expect(res.type).toBe("error");
  });

  it("answers an uncached static asset with a network error, never a rejection", async () => {
    const res = await respond("https://avenyth.de/_next/static/chunks/app.js", offline);
    expect(res).toBeInstanceOf(Response);
    expect(res.type).toBe("error");
  });

  it("passes a network 404 through unchanged", async () => {
    const res = await respond("https://avenyth.de/health_check.json", async () => new Response("", { status: 404 }));
    expect(res.status).toBe(404);
  });
});
