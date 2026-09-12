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
  const response = await fetcher(`${apiOrigin}/v1/config/public`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`public configuration request failed (${response.status})`);
  }

  const body = await response.json();
  if (
    typeof body !== "object" ||
    body === null ||
    !("brand_name" in body) ||
    typeof body.brand_name !== "string" ||
    body.brand_name.trim().length === 0 ||
    !("allow_self_signup" in body) ||
    typeof body.allow_self_signup !== "boolean"
  ) {
    throw new Error("invalid public configuration response");
  }

  return {
    brandName: body.brand_name,
    allowSelfSignup: body.allow_self_signup,
  };
}
