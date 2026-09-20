import { NextResponse, type NextRequest } from "next/server";

/** A fresh request nonce is forwarded to Next's renderer and sent to the browser.
 * Page HTML must be dynamic (root layout), never cached with a stale nonce.
 * Authorization remains exclusively in the API, not this middleware.
 */
export function middleware(request: NextRequest) {
  const nonce = btoa(crypto.randomUUID());
  const csp = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${process.env.NODE_ENV === "development" ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'", "img-src 'self' data:", "font-src 'self'",
    "object-src 'none'", "base-uri 'self'", "form-action 'self'",
    "frame-ancestors 'none'", "connect-src 'self'", "worker-src 'self'",
  ].join("; ");
  const headers = new Headers(request.headers);
  headers.set("Content-Security-Policy", csp);
  headers.set("x-nonce", nonce);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set("Content-Security-Policy", csp);
  // HSTS: both live surfaces terminate TLS (the Tailscale tunnel), so a browser
  // that ever reached this host over plaintext must not be allowed to stay there.
  // `includeSubDomains` is deliberately omitted -- the tunnel's sub-zone is not
  // ours to commit, and `preload` is a one-way door that needs a domain decision.
  response.headers.set("Strict-Transport-Security", "max-age=31536000");
  response.headers.set("Cache-Control", "private, no-store");
  return response;
}

export const config = { matcher: ["/((?!api/|_next/|favicon.ico|manifest.webmanifest|sw.js|icons/).*)"] };
