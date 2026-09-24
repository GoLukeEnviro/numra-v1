export interface MobilePublicConfig {
  brandName: string;
  allowSelfSignup: boolean;
}

interface FetchResponse {
  ok: boolean;
  status: number;
  json(): Promise<unknown>;
}

export type Fetcher = (
  input: string,
  init: { headers: { Accept: string } },
) => Promise<FetchResponse>;

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "10.0.2.2"]);

export function resolveApiOrigin(value: string | undefined): string {
  if (!value?.trim()) {
    throw new Error("EXPO_PUBLIC_API_URL is required");
  }

  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error("EXPO_PUBLIC_API_URL must be a valid absolute URL");
  }

  if (url.protocol !== "https:" && !(url.protocol === "http:" && LOCAL_HOSTS.has(url.hostname))) {
    throw new Error("EXPO_PUBLIC_API_URL must use HTTPS outside local development");
  }

  if (url.pathname !== "/" || url.search || url.hash || url.username || url.password) {
    throw new Error("EXPO_PUBLIC_API_URL must contain only the service origin");
  }

  return url.origin;
}

export async function loadPublicConfig(
  apiOrigin: string,
  fetcher: Fetcher = fetch as Fetcher,
): Promise<MobilePublicConfig> {
  // Contract: apps/api/src/numra_api/routes/public.py + PublicConfigOut. The web
  // client (apps/web/src/api/client.ts) already consumes this same endpoint/shape
  // via the generated OpenAPI type -- this must stay in sync with that, not with a
  // shape of its own.
  const response = await fetcher(`${apiOrigin}/v1/public/config`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`public configuration request failed (${response.status})`);
  }

  const body = await response.json();
  if (
    typeof body !== "object" ||
    body === null ||
    !("app_name" in body) ||
    typeof body.app_name !== "string" ||
    body.app_name.trim().length === 0 ||
    !("self_signup_enabled" in body) ||
    typeof body.self_signup_enabled !== "boolean"
  ) {
    throw new Error("invalid public configuration response");
  }

  return {
    brandName: body.app_name,
    allowSelfSignup: body.self_signup_enabled,
  };
}
