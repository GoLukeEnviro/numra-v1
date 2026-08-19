import type { components } from "@numra/schema";

export type LoginRequest = components["schemas"]["LoginRequest"];
export type UserOut = components["schemas"]["UserOut"];
export type PersonInput = components["schemas"]["PersonInput"];
export type PersonOut = components["schemas"]["PersonOut"];
export type PersonPatchRequest = components["schemas"]["PersonPatchRequest"];
export type CalculateRequest = components["schemas"]["CalculateRequest"];
export type CalculationOut = components["schemas"]["CalculationOut"];
export type RelationshipCreateRequest = components["schemas"]["RelationshipCreateRequest"];
export type RelationshipOut = components["schemas"]["RelationshipOut"];
export type BirthPlace = components["schemas"]["BirthPlace"];
export type BirthTime = components["schemas"]["BirthTime"];
export type BirthTimePrecision = components["schemas"]["BirthTimePrecision"];

const API_BASE_URL =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_BASE_URL) ||
  "http://localhost:8000";

/**
 * Structured API error. The API surfaces business errors as `{code, message}`
 * and FastAPI validation failures (422) as `{detail: ValidationError[]}` — this
 * class normalizes both into a single shape the UI can render consistently.
 */
export class ApiError extends Error {
  code: string;
  status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

export class NetworkError extends Error {
  constructor(cause: unknown) {
    super("Die Verbindung zum Server ist fehlgeschlagen.");
    this.name = "NetworkError";
    this.cause = cause;
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

const MUTATING_METHODS = new Set(["POST", "PATCH", "DELETE", "PUT"]);

interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, string | undefined>;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const url = new URL(path, API_BASE_URL);
  if (options.query) {
    for (const [key, value] of Object.entries(options.query)) {
      if (value !== undefined) url.searchParams.set(key, value);
    }
  }

  const headers: Record<string, string> = {};
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (MUTATING_METHODS.has(method)) {
    const csrf = readCookie("numra_csrf");
    if (csrf) headers["x-csrf-token"] = csrf;
  }

  let response: Response;
  try {
    response = await fetch(url.toString(), {
      method,
      headers,
      credentials: "include",
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch (cause) {
    throw new NetworkError(cause);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  const payload: unknown = contentType.includes("application/json")
    ? await response.json().catch(() => null)
    : null;

  if (!response.ok) {
    throw new ApiError(...extractError(payload, response.status));
  }

  return payload as T;
}

function extractError(payload: unknown, status: number): [string, string, number] {
  if (payload && typeof payload === "object") {
    const obj = payload as Record<string, unknown>;
    if (typeof obj.code === "string" && typeof obj.message === "string") {
      return [obj.message, obj.code, status];
    }
    if (Array.isArray(obj.detail) && obj.detail.length > 0) {
      const first = obj.detail[0] as { msg?: string; loc?: (string | number)[] };
      const field = Array.isArray(first.loc) ? first.loc.slice(1).join(".") : undefined;
      const msg = first.msg ?? "Validation failed";
      return [field ? `${field}: ${msg}` : msg, "VALIDATION_ERROR", status];
    }
  }
  if (status === 401) return ["Not authenticated.", "UNAUTHENTICATED", status];
  if (status === 403) return ["Not authorized.", "FORBIDDEN", status];
  if (status === 404) return ["Not found.", "NOT_FOUND", status];
  return [`Request failed with status ${status}.`, "UNKNOWN_ERROR", status];
}

export const api = {
  auth: {
    login: (body: LoginRequest) => request<UserOut>("/v1/auth/login", { method: "POST", body }),
    register: (body: LoginRequest) =>
      request<UserOut>("/v1/auth/register", { method: "POST", body }),
    logout: () => request<void>("/v1/auth/logout", { method: "POST" }),
    me: () => request<UserOut>("/v1/auth/me"),
  },
  people: {
    list: () => request<PersonOut[]>("/v1/people"),
    get: (personId: string) => request<PersonOut>(`/v1/people/${personId}`),
    create: (body: PersonInput) => request<PersonOut>("/v1/people", { method: "POST", body }),
    patch: (personId: string, body: PersonPatchRequest) =>
      request<PersonOut>(`/v1/people/${personId}`, { method: "PATCH", body }),
    remove: (personId: string) =>
      request<void>(`/v1/people/${personId}`, { method: "DELETE" }),
    timing: (personId: string, asOfDate: string) =>
      request<Record<string, unknown>>(`/v1/people/${personId}/timing`, {
        query: { as_of_date: asOfDate },
      }),
  },
  calculations: {
    create: (personId: string, body: CalculateRequest) =>
      request<CalculationOut>(`/v1/people/${personId}/calculations`, {
        method: "POST",
        body,
      }),
    get: (calculationId: string) =>
      request<CalculationOut>(`/v1/calculations/${calculationId}`),
  },
  relationships: {
    create: (body: RelationshipCreateRequest) =>
      request<RelationshipOut>("/v1/relationships", { method: "POST", body }),
    get: (relationshipId: string) =>
      request<RelationshipOut>(`/v1/relationships/${relationshipId}`),
  },
};
