import { isIP } from "node:net";

/** Server-only helpers for the same-origin API proxy (app/api/[...path]/route.ts).
 * Nothing here may be imported by client code: it reads the shared proxy secret. */

const HOP_BY_HOP_REQUEST_HEADERS = new Set(["host", "connection", "content-length"]);

/** Headers a client could use to claim an identity/origin the BFF alone may assert. */
const STRIPPED_EXACT = new Set([
  "forwarded",
  "x-real-ip",
  "x-client-ip",
  "true-client-ip",
  "cf-connecting-ip",
  "x-user-id",
  "x-user",
]);
const STRIPPED_PREFIXES = ["x-numra-", "x-forwarded-"];

export const PROXY_AUTH_HEADER = "x-numra-proxy-auth";

export interface ProxyConfig {
  secret: string | undefined;
  /** Number of trusted reverse proxies in front of this server (0 = forward no client IP). */
  trustedHops: number;
}

const MIN_SECRET_LENGTH = 32;

export function readProxyConfig(env: NodeJS.ProcessEnv = process.env): ProxyConfig {
  const hops = Number.parseInt(env.TRUSTED_PROXY_HOPS ?? "0", 10);
  const secret = env.INTERNAL_PROXY_SHARED_SECRET || undefined;
  // Same floor as the API's Settings; a padded/short secret is a deployment error that
  // must be loud (every proxied request fails), never silently weak or silently unsent.
  if (secret !== undefined && (secret !== secret.trim() || secret.length < MIN_SECRET_LENGTH)) {
    throw new Error(
      `INTERNAL_PROXY_SHARED_SECRET must be at least ${MIN_SECRET_LENGTH} characters without surrounding whitespace`,
    );
  }
  return {
    secret,
    trustedHops: Number.isInteger(hops) && hops > 0 ? hops : 0,
  };
}

function isStripped(name: string): boolean {
  return STRIPPED_EXACT.has(name) || STRIPPED_PREFIXES.some((prefix) => name.startsWith(prefix));
}

/** The client IP as appended by the Nth proxy from the right of X-Forwarded-For. The
 * left-hand entries are client-controlled and never used. */
export function resolveClientIp(incoming: Headers, trustedHops: number): string | undefined {
  if (trustedHops < 1) return undefined;
  const entries = (incoming.get("x-forwarded-for") ?? "").split(",").map((part) => part.trim());
  const candidate = entries[entries.length - trustedHops];
  return candidate && isIP(candidate) ? candidate : undefined;
}

export function buildUpstreamHeaders(incoming: Headers, config: ProxyConfig): Headers {
  const clientIp = resolveClientIp(incoming, config.trustedHops);
  const upstream = new Headers();
  incoming.forEach((value, key) => {
    const name = key.toLowerCase();
    if (!HOP_BY_HOP_REQUEST_HEADERS.has(name) && !isStripped(name)) upstream.set(key, value);
  });
  if (config.secret) {
    upstream.set(PROXY_AUTH_HEADER, config.secret);
    if (clientIp) upstream.set("x-forwarded-for", clientIp);
  }
  return upstream;
}
