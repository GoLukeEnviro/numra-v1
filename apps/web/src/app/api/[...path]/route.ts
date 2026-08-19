import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Same-origin API proxy: the browser only ever calls /api/*; this Route Handler
 * forwards each request to API_INTERNAL_URL (a plain, non-NEXT_PUBLIC_ env var) and
 * streams the response back verbatim, including every Set-Cookie header (session/CSRF
 * auth depends on this — see the getSetCookie() note below).
 *
 * Deliberately NOT implemented via next.config.mjs's rewrites(): that async function
 * is evaluated once at `next build` time and its result is baked into
 * .next/routes-manifest.json, so an env var read there is NOT re-read at `next start`
 * — the whole point of this proxy (one built image, runtime-configurable backend URL)
 * would silently not work. A Route Handler's function body genuinely runs fresh on
 * every request, so `process.env.API_INTERNAL_URL` here really is read at request
 * time.
 */
export const dynamic = "force-dynamic";

const HOP_BY_HOP_REQUEST_HEADERS = new Set(["host", "connection", "content-length"]);
const HOP_BY_HOP_RESPONSE_HEADERS = new Set(["content-encoding", "content-length", "connection"]);

async function proxy(
  request: NextRequest,
  context: { params: { path: string[] } },
): Promise<NextResponse> {
  const apiInternalUrl = process.env.API_INTERNAL_URL || "http://api:8000";
  const path = context.params.path.join("/");
  const targetUrl = new URL(`/${path}${request.nextUrl.search}`, apiInternalUrl);

  const requestHeaders = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP_REQUEST_HEADERS.has(key.toLowerCase())) requestHeaders.set(key, value);
  });

  const hasBody = !["GET", "HEAD"].includes(request.method);

  let upstreamResponse: Response;
  try {
    upstreamResponse = await fetch(targetUrl, {
      method: request.method,
      headers: requestHeaders,
      body: hasBody ? await request.arrayBuffer() : undefined,
      redirect: "manual",
      // @ts-expect-error -- Node's fetch requires this for a request carrying a body.
      duplex: hasBody ? "half" : undefined,
    });
  } catch {
    return NextResponse.json(
      { code: "UPSTREAM_UNAVAILABLE", message: "Could not reach the API." },
      { status: 502 },
    );
  }

  const responseHeaders = new Headers();
  upstreamResponse.headers.forEach((value, key) => {
    if (!HOP_BY_HOP_RESPONSE_HEADERS.has(key.toLowerCase())) responseHeaders.set(key, value);
  });
  // Headers collapses multiple Set-Cookie values into one comma-joined string when
  // iterated normally (per the Fetch spec) -- getSetCookie() is the one API that
  // returns them as a real array, which is required here since a single response can
  // set both the session and CSRF cookies at once (see numra_api's _set_auth_cookies).
  responseHeaders.delete("set-cookie");
  for (const cookie of upstreamResponse.headers.getSetCookie()) {
    responseHeaders.append("set-cookie", cookie);
  }

  return new NextResponse(upstreamResponse.body, {
    status: upstreamResponse.status,
    headers: responseHeaders,
  });
}

export {
  proxy as GET,
  proxy as POST,
  proxy as PATCH,
  proxy as DELETE,
  proxy as PUT,
  proxy as OPTIONS,
};
