export interface MobileUser {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  email_verified_at?: string | null;
}

export interface TokenStore {
  get(): Promise<string | null>;
  set(value: string): Promise<void>;
  delete(): Promise<void>;
}

interface ResponseLike { ok: boolean; status: number; json(): Promise<unknown> }
type AuthFetcher = (input: string, init: RequestInit) => Promise<ResponseLike>;

function isUser(value: unknown): value is MobileUser {
  return typeof value === "object" && value !== null &&
    "id" in value && typeof value.id === "string" &&
    "email" in value && typeof value.email === "string" &&
    "role" in value && typeof value.role === "string" &&
    "is_active" in value && typeof value.is_active === "boolean";
}

export function createAuthClient(origin: string, store: TokenStore, fetcher: AuthFetcher = fetch) {
  const bearer = (token: string) => ({ Authorization: `Bearer ${token}`, Accept: "application/json" });

  return {
    async login(email: string, password: string): Promise<MobileUser> {
      const response = await fetcher(`${origin}/v1/auth/mobile/login`, {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(response.status === 401 ? "INVALID_CREDENTIALS" : "LOGIN_FAILED");
      if (typeof payload !== "object" || payload === null || !("access_token" in payload) ||
          typeof payload.access_token !== "string" || !("user" in payload) || !isUser(payload.user)) {
        throw new Error("INVALID_LOGIN_RESPONSE");
      }
      await store.set(payload.access_token);
      return payload.user;
    },

    async restore(): Promise<MobileUser | null> {
      const token = await store.get();
      if (!token) return null;
      const response = await fetcher(`${origin}/v1/auth/mobile/me`, { headers: bearer(token) });
      if (response.status === 401) {
        await store.delete();
        return null;
      }
      if (!response.ok) throw new Error("SESSION_RESTORE_FAILED");
      const payload = await response.json();
      if (!isUser(payload)) throw new Error("INVALID_USER_RESPONSE");
      return payload;
    },

    async logout(): Promise<void> {
      const token = await store.get();
      try {
        if (token) {
          const response = await fetcher(`${origin}/v1/auth/mobile/logout`, {
            method: "POST",
            headers: bearer(token),
          });
          if (!response.ok && response.status !== 401) throw new Error("LOGOUT_FAILED");
        }
      } finally {
        await store.delete();
      }
    },
  };
}
