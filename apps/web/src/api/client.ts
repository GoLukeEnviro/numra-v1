import type { components } from "@numra/schema";

export type LoginRequest = components["schemas"]["LoginRequest"];
export type RegisterRequest = components["schemas"]["RegisterRequest"];
export type PublicConfigOut = components["schemas"]["PublicConfigOut"];
export type UserOut = components["schemas"]["UserOut"];
// PersonCreateRequest (POST /v1/people body) supersedes the engine-only PersonInput
// schema with an app-level `person_account_mode` field (specs/v2/minor-profile-policy.md).
// Kept as `PersonInput` here to avoid touching every existing caller of this alias.
export type PersonInput = components["schemas"]["PersonCreateRequest"];
export type PersonOut = components["schemas"]["PersonOut"];
export type PersonPatchRequest = components["schemas"]["PersonPatchRequest"];
export type NameIdentityOut = components["schemas"]["NameIdentityOut"];
export type NameIdentityKind = components["schemas"]["NameIdentityKind"];
export type CalculateRequest = components["schemas"]["CalculateRequest"];
export type CalculationOut = components["schemas"]["CalculationOut"];
export type CalculationSummaryOut = components["schemas"]["CalculationSummaryOut"];
export type RelationshipCreateRequest = components["schemas"]["RelationshipCreateRequest"];
export type RelationshipOut = components["schemas"]["RelationshipOut"];
export type RelationshipSummaryOut = components["schemas"]["RelationshipSummaryOut"];
export type RelationshipInsightOut = components["schemas"]["RelationshipInsightOut"];
export type DailyBriefOut = components["schemas"]["DailyBriefOut"];
export type DailyBriefSectionOut = components["schemas"]["DailyBriefSectionOut"];
export type PersonRefOut = components["schemas"]["PersonRefOut"];
export type BirthPlace = components["schemas"]["BirthPlace"];
export type BirthTime = components["schemas"]["BirthTime"];
export type BirthTimePrecision = components["schemas"]["BirthTimePrecision"];
export type ReportCreateRequest = components["schemas"]["ReportCreateRequest"];
export type ReportOut = components["schemas"]["ReportOut"];
export type ReportSummaryOut = components["schemas"]["ReportSummaryOut"];
export type ReportJobOut = components["schemas"]["ReportJobOut"];
export type ReportJobStatus = components["schemas"]["ReportJobStatus"];
export type ReportType = components["schemas"]["ReportType"];
export type ExportCreateRequest = components["schemas"]["ExportCreateRequest"];
export type ExportOut = components["schemas"]["ExportOut"];
export type ExportStatus = components["schemas"]["ExportStatus"];
export type DeleteAccountRequest = components["schemas"]["DeleteAccountRequest"];
export type ChangePasswordRequest = components["schemas"]["ChangePasswordRequest"];
export type VerifyEmailRequest = components["schemas"]["VerifyEmailRequest"];
export type ForgotPasswordRequest = components["schemas"]["ForgotPasswordRequest"];
export type ResetPasswordRequest = components["schemas"]["ResetPasswordRequest"];
export type SessionOut = components["schemas"]["SessionOut"];
export type SystemInfoOut = components["schemas"]["SystemInfoOut"];
export type UserRole = components["schemas"]["UserRole"];
export type AdminStatsOut = components["schemas"]["AdminStatsOut"];
export type AdminUserOut = components["schemas"]["AdminUserOut"];
export type AdminUserListOut = components["schemas"]["AdminUserListOut"];
export type AuditAction = components["schemas"]["AuditAction"];
export type AuditEventOut = components["schemas"]["AuditEventOut"];
export type AuditEventListOut = components["schemas"]["AuditEventListOut"];

// V2 Web/PWA schema types (PR-WEB-00) -- see the api.connections/api.workspaces/etc.
// block comment below for why these are typed now but unused until later PRs.
export type UserConnectionOut = components["schemas"]["UserConnectionOut"];
export type ConnectionInvitationCreateRequest =
  components["schemas"]["ConnectionInvitationCreateRequest"];
export type ConnectionInvitationCreatedOut =
  components["schemas"]["ConnectionInvitationCreatedOut"];
export type ConnectionInvitationOut = components["schemas"]["ConnectionInvitationOut"];
export type ConnectionInvitationPreviewOut =
  components["schemas"]["ConnectionInvitationPreviewOut"];
export type RedeemInvitationRequest = components["schemas"]["RedeemInvitationRequest"];
export type RedeemInvitationResponseOut = components["schemas"]["RedeemInvitationResponseOut"];
export type InvitationMethod = components["schemas"]["InvitationMethod"];
export type InvitationState = components["schemas"]["InvitationState"];
export type ConnectionStatus = components["schemas"]["ConnectionStatus"];
export type ConsentScope = components["schemas"]["ConsentScope"];

export type WorkspaceSummaryOut = components["schemas"]["WorkspaceSummaryOut"];
export type WorkspaceOut = components["schemas"]["WorkspaceOut"];
export type WorkspaceUpdateRequest = components["schemas"]["WorkspaceUpdateRequest"];
/** GET /v1/workspaces/{id} response -- module-qualified in the generated schema
 *  because a second, differently-shaped `WorkspaceOverviewOut` exists for
 *  GET /v1/me/workspace (see `MyWorkspaceOverviewOut` below). */
export type WorkspaceOverviewOut =
  components["schemas"]["numra_api__schemas__relationship_workspace__WorkspaceOverviewOut"];
/** GET /v1/me/workspace response (the Personal Workspace index). */
export type MyWorkspaceOverviewOut =
  components["schemas"]["numra_api__schemas__workspace__WorkspaceOverviewOut"];

export type CheckinDimensionCreateRequest =
  components["schemas"]["CheckinDimensionCreateRequest"];
export type CheckinDimensionOut = components["schemas"]["CheckinDimensionOut"];
export type CheckinDimensionUpdateRequest =
  components["schemas"]["CheckinDimensionUpdateRequest"];
export type CheckinTemplateOut = components["schemas"]["CheckinTemplateOut"];
export type CheckinSummaryOut = components["schemas"]["CheckinSummaryOut"];
export type CheckinSubmitRequest = components["schemas"]["CheckinSubmitRequest"];
export type CheckinOut = components["schemas"]["CheckinOut"];

export type WorkspaceConsentOut = components["schemas"]["WorkspaceConsentOut"];
export type ConsentGrantRequest = components["schemas"]["ConsentGrantRequest"];
export type ConsentGrantOut = components["schemas"]["ConsentGrantOut"];
export type ConsentRevokeRequest = components["schemas"]["ConsentRevokeRequest"];

export type ChatThreadOut = components["schemas"]["ChatThreadOut"];
export type ThreadCreateRequest = components["schemas"]["ThreadCreateRequest"];
export type ChatMessageOut = components["schemas"]["ChatMessageOut"];
export type MessageCreateRequest = components["schemas"]["MessageCreateRequest"];
export type MessagePairOut = components["schemas"]["MessagePairOut"];

export type RelationshipRoadmapOut = components["schemas"]["RelationshipRoadmapOut"];
export type RelationshipRoadmapCreateRequest =
  components["schemas"]["RelationshipRoadmapCreateRequest"];
export type RelationshipRoadmapPatchRequest =
  components["schemas"]["RelationshipRoadmapPatchRequest"];
export type RoadmapMilestoneOut = components["schemas"]["RoadmapMilestoneOut"];
export type RoadmapMilestoneCreateRequest = components["schemas"]["RoadmapMilestoneCreateRequest"];
export type RoadmapMilestonePatchRequest = components["schemas"]["RoadmapMilestonePatchRequest"];
export type MilestoneType = components["schemas"]["MilestoneType"];

export type WorkspaceTaskOut = components["schemas"]["WorkspaceTaskOut"];
export type WorkspaceTaskCreateRequest = components["schemas"]["WorkspaceTaskCreateRequest"];
export type WorkspaceTaskPatchRequest = components["schemas"]["WorkspaceTaskPatchRequest"];
export type WorkspaceTaskStatus = components["schemas"]["WorkspaceTaskStatus"];
export type TaskType = components["schemas"]["TaskType"];

export type PersonalTaskOut = components["schemas"]["PersonalTaskOut"];
export type PersonalTaskCreateRequest = components["schemas"]["PersonalTaskCreateRequest"];
export type PersonalTaskPatchRequest = components["schemas"]["PersonalTaskPatchRequest"];
export type PersonalTaskStatus = components["schemas"]["PersonalTaskStatus"];

export type PrivateNoteOut = components["schemas"]["PrivateNoteOut"];
export type PrivateNoteCreateRequest = components["schemas"]["PrivateNoteCreateRequest"];
export type PrivateNotePatchRequest = components["schemas"]["PrivateNotePatchRequest"];

export type PrivateReflectionOut = components["schemas"]["PrivateReflectionOut"];
export type PrivateReflectionCreateRequest =
  components["schemas"]["PrivateReflectionCreateRequest"];
export type PrivateReflectionPatchRequest =
  components["schemas"]["PrivateReflectionPatchRequest"];
export type SharePrivateReflectionRequest = components["schemas"]["SharePrivateReflectionRequest"];
export type SharedReflectionOut = components["schemas"]["SharedReflectionOut"];

/**
 * `LifeTrackingEntry*` verified directly against packages/schema/src/generated/
 * schema.d.ts's `paths` section (PR-WEB-00 blueprint's exact-path caveat): the list/
 * create routes are person-scoped (`/v1/people/{person_id}/life-tracking-entries`),
 * get/patch/delete are flat (`/v1/life-tracking-entries/{entry_id}`) -- mirroring the
 * personal-tasks/private-notes/private-reflections split already in this file.
 */
export type LifeTrackingEntryOut = components["schemas"]["LifeTrackingEntryOut"];
export type LifeTrackingEntryCreateRequest =
  components["schemas"]["LifeTrackingEntryCreateRequest"];
export type LifeTrackingEntryPatchRequest =
  components["schemas"]["LifeTrackingEntryPatchRequest"];

export type EntitlementSetOut = components["schemas"]["EntitlementSetOut"];

/** V1.6: server-side filtering/pagination for `GET /v1/admin/users`. */
export interface AdminUserListParams {
  search?: string;
  role?: UserRole;
  isActive?: boolean;
  page?: number;
  pageSize?: number;
}

/** V1.6: server-side filtering/pagination for `GET /v1/admin/audit`. */
export interface AdminAuditListParams {
  action?: string;
  targetUserId?: string;
  page?: number;
  pageSize?: number;
}

// Same-origin only: every request goes to /api/*, which next.config.mjs's rewrite
// forwards server-side to API_INTERNAL_URL (a runtime, non-NEXT_PUBLIC_ env var — see
// that file's comment). The browser never needs to know the real backend origin, and
// no build-time-baked API URL means the same built image works across environments.
const API_PREFIX = "/api";

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
  /** Extra request headers (e.g. `Idempotency-Key`). CSRF is still added automatically. */
  headers?: Record<string, string>;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const origin = typeof window !== "undefined" ? window.location.origin : "http://localhost";
  const url = new URL(`${API_PREFIX}${path}`, origin);
  if (options.query) {
    for (const [key, value] of Object.entries(options.query)) {
      if (value !== undefined) url.searchParams.set(key, value);
    }
  }

  const headers: Record<string, string> = { ...options.headers };
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
    register: (body: RegisterRequest) =>
      request<UserOut>("/v1/auth/register", { method: "POST", body }),
    logout: () => request<void>("/v1/auth/logout", { method: "POST" }),
    me: () => request<UserOut>("/v1/auth/me"),
    /** V1.5 Epic N. Revokes every other active session; the caller's own session
     *  stays valid, so this never signs the caller themselves out. */
    changePassword: (body: ChangePasswordRequest) =>
      request<void>("/v1/auth/change-password", { method: "POST", body }),
    /** V1.5 Epic N. Every currently active session for this user, newest first. */
    sessions: () => request<SessionOut[]>("/v1/auth/sessions"),
    /** V1.5 Epic N. "Log out other devices" -- revokes every session but this one. */
    revokeOtherSessions: () =>
      request<void>("/v1/auth/sessions/revoke-others", { method: "POST" }),
    /** V2: (re-)sends a verification link to the signed-in user's own email address. */
    requestEmailVerification: () =>
      request<void>("/v1/auth/request-email-verification", { method: "POST" }),
    /** V2: unauthenticated -- the token itself is the proof of ownership. */
    verifyEmail: (body: VerifyEmailRequest) =>
      request<void>("/v1/auth/verify-email", { method: "POST", body }),
    /** V2: always resolves (202/204) regardless of whether the address exists --
     *  anti-enumeration, see backend docstring on the matching route. */
    forgotPassword: (body: ForgotPasswordRequest) =>
      request<void>("/v1/auth/forgot-password", { method: "POST", body }),
    resetPassword: (body: ResetPasswordRequest) =>
      request<void>("/v1/auth/reset-password", { method: "POST", body }),
  },
  /** V1.6 B: anonymous bootstrap config for the pre-login pages. */
  publicConfig: {
    get: () => request<PublicConfigOut>("/v1/public/config"),
  },
  systemInfo: {
    get: () => request<SystemInfoOut>("/v1/system-info"),
  },
  people: {
    list: () => request<PersonOut[]>("/v1/people"),
    get: (personId: string) => request<PersonOut>(`/v1/people/${personId}`),
    create: (body: PersonInput) => request<PersonOut>("/v1/people", { method: "POST", body }),
    patch: (personId: string, body: PersonPatchRequest) =>
      request<PersonOut>(`/v1/people/${personId}`, { method: "PATCH", body }),
    remove: (personId: string) =>
      request<void>(`/v1/people/${personId}`, { method: "DELETE" }),
    /**
     * Ad-hoc timing lookup. The backend declares this endpoint as a bare dict
     * (routes/calculations.py::get_timing_route returns `profile["timing"]`), so no
     * response schema is generated for it — the payload is returned as `unknown` and
     * narrowed by `asTiming()` in api/canonical-profile.ts, exactly like
     * `canonical_profile` is narrowed by `asCanonicalProfile()`.
     */
    timing: (personId: string, asOfDate: string) =>
      request<unknown>(`/v1/people/${personId}/timing`, {
        query: { as_of_date: asOfDate },
      }),
    /**
     * V1.5 Epic K: the deterministic, reproducible Daily Brief -- Personal Day/
     * Month/Year with knowledge-sourced reflection text. Ad-hoc, non-persisted,
     * same pattern as timing() above.
     */
    dailyBrief: (personId: string, asOfDate: string) =>
      request<DailyBriefOut>(`/v1/people/${personId}/daily-brief`, {
        query: { as_of_date: asOfDate },
      }),
    /** V1.5 Epic C: the real, server-recorded name history for this person. */
    identities: (personId: string) =>
      request<NameIdentityOut[]>(`/v1/people/${personId}/identities`),
    // V2 (PR-WEB-00): person-scoped private data. Get/patch/delete are flat routes
    // (`/v1/private-notes/{id}`, not nested under the person), matching personal-tasks.
    privateNotes: {
      list: (personId: string, params: { limit?: number; offset?: number } = {}) =>
        request<PrivateNoteOut[]>(`/v1/people/${personId}/private-notes`, {
          query: {
            limit: params.limit === undefined ? undefined : String(params.limit),
            offset: params.offset === undefined ? undefined : String(params.offset),
          },
        }),
      create: (personId: string, body: PrivateNoteCreateRequest) =>
        request<PrivateNoteOut>(`/v1/people/${personId}/private-notes`, {
          method: "POST",
          body,
        }),
      get: (noteId: string) => request<PrivateNoteOut>(`/v1/private-notes/${noteId}`),
      patch: (noteId: string, body: PrivateNotePatchRequest) =>
        request<PrivateNoteOut>(`/v1/private-notes/${noteId}`, { method: "PATCH", body }),
      remove: (noteId: string) =>
        request<void>(`/v1/private-notes/${noteId}`, { method: "DELETE" }),
    },
    privateReflections: {
      list: (personId: string, params: { limit?: number; offset?: number } = {}) =>
        request<PrivateReflectionOut[]>(`/v1/people/${personId}/private-reflections`, {
          query: {
            limit: params.limit === undefined ? undefined : String(params.limit),
            offset: params.offset === undefined ? undefined : String(params.offset),
          },
        }),
      create: (personId: string, body: PrivateReflectionCreateRequest) =>
        request<PrivateReflectionOut>(`/v1/people/${personId}/private-reflections`, {
          method: "POST",
          body,
        }),
      get: (reflectionId: string) =>
        request<PrivateReflectionOut>(`/v1/private-reflections/${reflectionId}`),
      patch: (reflectionId: string, body: PrivateReflectionPatchRequest) =>
        request<PrivateReflectionOut>(`/v1/private-reflections/${reflectionId}`, {
          method: "PATCH",
          body,
        }),
      remove: (reflectionId: string) =>
        request<void>(`/v1/private-reflections/${reflectionId}`, { method: "DELETE" }),
      share: (reflectionId: string, body: SharePrivateReflectionRequest) =>
        request<SharedReflectionOut>(`/v1/private-reflections/${reflectionId}/share`, {
          method: "POST",
          body,
        }),
    },
    // Path verified against packages/schema/src/generated/schema.d.ts's `paths`
    // section (PR-WEB-00 blueprint's exact-path caveat): `-entries` suffix on both
    // segments, i.e. `/v1/people/{person_id}/life-tracking-entries` (list/create) and
    // the flat `/v1/life-tracking-entries/{entry_id}` (get/patch/delete) -- not
    // `/life-tracking` as the plain feature name might suggest.
    lifeTracking: {
      list: (
        personId: string,
        params: { from?: string; to?: string; limit?: number; offset?: number } = {},
      ) =>
        request<LifeTrackingEntryOut[]>(`/v1/people/${personId}/life-tracking-entries`, {
          query: {
            from: params.from,
            to: params.to,
            limit: params.limit === undefined ? undefined : String(params.limit),
            offset: params.offset === undefined ? undefined : String(params.offset),
          },
        }),
      create: (personId: string, body: LifeTrackingEntryCreateRequest) =>
        request<LifeTrackingEntryOut>(`/v1/people/${personId}/life-tracking-entries`, {
          method: "POST",
          body,
        }),
      get: (entryId: string) =>
        request<LifeTrackingEntryOut>(`/v1/life-tracking-entries/${entryId}`),
      patch: (entryId: string, body: LifeTrackingEntryPatchRequest) =>
        request<LifeTrackingEntryOut>(`/v1/life-tracking-entries/${entryId}`, {
          method: "PATCH",
          body,
        }),
      remove: (entryId: string) =>
        request<void>(`/v1/life-tracking-entries/${entryId}`, { method: "DELETE" }),
    },
  },
  calculations: {
    create: (personId: string, body: CalculateRequest) =>
      request<CalculationOut>(`/v1/people/${personId}/calculations`, {
        method: "POST",
        body,
      }),
    get: (calculationId: string) =>
      request<CalculationOut>(`/v1/calculations/${calculationId}`),
    /** Calculation history for a person — server-authoritative, newest first. */
    list: (personId: string) =>
      request<CalculationSummaryOut[]>(`/v1/people/${personId}/calculations`),
  },
  relationships: {
    create: (body: RelationshipCreateRequest) =>
      request<RelationshipOut>("/v1/relationships", { method: "POST", body }),
    get: (relationshipId: string) =>
      request<RelationshipOut>(`/v1/relationships/${relationshipId}`),
    /** The relationship library — server-authoritative, resolved person names. */
    list: () => request<RelationshipSummaryOut[]>("/v1/relationships"),
  },
  reports: {
    /**
     * Starts a long-form report generation job. `idempotencyKey` maps to the
     * optional `Idempotency-Key` header the endpoint honours, so a double-submit
     * (double click, retried request) reuses the first job instead of queueing a
     * second identical generation.
     */
    create: (body: ReportCreateRequest, idempotencyKey?: string) =>
      request<ReportOut>("/v1/reports", {
        method: "POST",
        body,
        headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined,
      }),
    get: (reportId: string) => request<ReportOut>(`/v1/reports/${reportId}`),
    getJob: (jobId: string) => request<ReportJobOut>(`/v1/report-jobs/${jobId}`),
    /** The report library — server-authoritative, optionally filtered. */
    list: (filter?: { personId?: string; calculationId?: string; status?: string }) =>
      request<ReportSummaryOut[]>("/v1/reports", {
        query: {
          person_id: filter?.personId,
          calculation_id: filter?.calculationId,
          status: filter?.status,
        },
      }),
  },
  exports: {
    /**
     * Synchronous: the API blocks until the PDF microservice has actually rendered
     * the file, so callers must show a real pending state rather than polling.
     */
    create: (body: ExportCreateRequest) =>
      request<ExportOut>("/v1/exports", { method: "POST", body }),
    list: () => request<ExportOut[]>("/v1/exports"),
    /**
     * A real file download (raw PDF bytes + Content-Disposition), not a JSON call —
     * this returns the same-origin path to link/navigate to directly, because routing
     * binary content through `request()`'s JSON handling would corrupt it.
     */
    downloadUrl: (exportId: string) => `${API_PREFIX}/v1/exports/${exportId}/download`,
  },
  account: {
    /** Irreversible: deletes every person, calculation, relationship, report and
     * export file for the current user, then invalidates the session server-side. */
    deleteAll: (body: DeleteAccountRequest) =>
      request<void>("/v1/account/delete-all", { method: "POST", body }),
  },
  /**
   * V1.6 admin console. Every endpoint here sits behind `require_admin` in the
   * FastAPI router — a non-admin session gets 403, an anonymous one 401. The
   * frontend's admin gating is convenience only; the API is the security boundary.
   */
  admin: {
    stats: () => request<AdminStatsOut>("/v1/admin/stats"),
    users: {
      /** Server-side search/filter/pagination — never filter the page client-side.
       *  `page_size` is capped at 100 by the API. */
      list: (params: AdminUserListParams = {}) =>
        request<AdminUserListOut>("/v1/admin/users", {
          query: {
            search: params.search || undefined,
            role: params.role,
            is_active: params.isActive === undefined ? undefined : String(params.isActive),
            page: params.page === undefined ? undefined : String(params.page),
            page_size: params.pageSize === undefined ? undefined : String(params.pageSize),
          },
        }),
      get: (userId: string) => request<AdminUserOut>(`/v1/admin/users/${userId}`),
      disable: (userId: string) =>
        request<void>(`/v1/admin/users/${userId}/disable`, { method: "POST" }),
      enable: (userId: string) =>
        request<void>(`/v1/admin/users/${userId}/enable`, { method: "POST" }),
      revokeSessions: (userId: string) =>
        request<void>(`/v1/admin/users/${userId}/revoke-sessions`, { method: "POST" }),
    },
    audit: {
      list: (params: AdminAuditListParams = {}) =>
        request<AuditEventListOut>("/v1/admin/audit", {
          query: {
            action: params.action || undefined,
            target_user_id: params.targetUserId || undefined,
            page: params.page === undefined ? undefined : String(params.page),
            page_size: params.pageSize === undefined ? undefined : String(params.pageSize),
          },
        }),
    },
  },
  // V2 Web/PWA namespaces (PR-WEB-00): fully typed against @numra/schema now,
  // consumed starting PR-WEB-02 (Personal Workspace) onward. Each PR that adds
  // a feature page wires exactly the namespace it needs -- this stub layer only
  // exists so the typed client and the OpenAPI contract stay in permanent sync
  // from day one, instead of every later PR re-deriving ad hoc request calls.
  connections: {
    list: (params: { limit?: number; offset?: number } = {}) =>
      request<UserConnectionOut[]>("/v1/connections", {
        query: {
          limit: params.limit === undefined ? undefined : String(params.limit),
          offset: params.offset === undefined ? undefined : String(params.offset),
        },
      }),
    invite: (body: ConnectionInvitationCreateRequest) =>
      request<ConnectionInvitationCreatedOut>("/v1/connections/invitations", {
        method: "POST",
        body,
      }),
    redeemInvitation: (body: RedeemInvitationRequest) =>
      request<RedeemInvitationResponseOut>("/v1/connections/invitations/redeem", {
        method: "POST",
        body,
      }),
    listInvitations: (params: { limit?: number; offset?: number } = {}) =>
      request<ConnectionInvitationOut[]>("/v1/connections/invitations", {
        query: {
          limit: params.limit === undefined ? undefined : String(params.limit),
          offset: params.offset === undefined ? undefined : String(params.offset),
        },
      }),
    previewByToken: (token: string) =>
      request<ConnectionInvitationPreviewOut>(
        `/v1/connections/invitations/redeem/${encodeURIComponent(token)}`,
      ),
    declineInvitation: (invitationId: string) =>
      request<ConnectionInvitationOut>(
        `/v1/connections/invitations/${invitationId}/decline`,
        { method: "POST" },
      ),
    revokeInvitation: (invitationId: string) =>
      request<ConnectionInvitationOut>(
        `/v1/connections/invitations/${invitationId}/revoke`,
        { method: "POST" },
      ),
    dissolve: (connectionId: string) =>
      request<UserConnectionOut>(`/v1/connections/${connectionId}/dissolve`, {
        method: "POST",
      }),
  },
  workspaces: {
    list: () => request<WorkspaceSummaryOut[]>("/v1/workspaces"),
    get: (workspaceId: string) =>
      request<WorkspaceOverviewOut>(`/v1/workspaces/${workspaceId}`),
    patch: (workspaceId: string, body: WorkspaceUpdateRequest) =>
      request<WorkspaceOut>(`/v1/workspaces/${workspaceId}`, { method: "PATCH", body }),
    consent: {
      list: (workspaceId: string) =>
        request<WorkspaceConsentOut>(`/v1/workspaces/${workspaceId}/consent`),
      grant: (workspaceId: string, body: ConsentGrantRequest) =>
        request<ConsentGrantOut>(`/v1/workspaces/${workspaceId}/consent/grant`, {
          method: "POST",
          body,
        }),
      revoke: (workspaceId: string, body: ConsentRevokeRequest) =>
        request<ConsentGrantOut>(`/v1/workspaces/${workspaceId}/consent/revoke`, {
          method: "POST",
          body,
        }),
    },
    checkinDimensions: {
      create: (workspaceId: string, body: CheckinDimensionCreateRequest) =>
        request<CheckinDimensionOut>(`/v1/workspaces/${workspaceId}/checkin-dimensions`, {
          method: "POST",
          body,
        }),
      update: (workspaceId: string, dimensionId: string, body: CheckinDimensionUpdateRequest) =>
        request<CheckinDimensionOut>(
          `/v1/workspaces/${workspaceId}/checkin-dimensions/${dimensionId}`,
          { method: "PATCH", body },
        ),
    },
    checkinTemplate: {
      get: (workspaceId: string) =>
        request<CheckinTemplateOut>(`/v1/workspaces/${workspaceId}/checkin-template`),
    },
    checkins: {
      list: (workspaceId: string, params: { limit?: number; offset?: number } = {}) =>
        request<CheckinSummaryOut[]>(`/v1/workspaces/${workspaceId}/checkins`, {
          query: {
            limit: params.limit === undefined ? undefined : String(params.limit),
            offset: params.offset === undefined ? undefined : String(params.offset),
          },
        }),
      submit: (workspaceId: string, body: CheckinSubmitRequest) =>
        request<CheckinOut>(`/v1/workspaces/${workspaceId}/checkins`, {
          method: "POST",
          body,
        }),
      get: (workspaceId: string, checkinId: string) =>
        request<CheckinOut>(`/v1/workspaces/${workspaceId}/checkins/${checkinId}`),
    },
    tasks: {
      list: (
        workspaceId: string,
        params: {
          status?: WorkspaceTaskStatus;
          taskType?: TaskType;
          limit?: number;
          offset?: number;
        } = {},
      ) =>
        request<WorkspaceTaskOut[]>(`/v1/workspaces/${workspaceId}/tasks`, {
          query: {
            status: params.status,
            task_type: params.taskType,
            limit: params.limit === undefined ? undefined : String(params.limit),
            offset: params.offset === undefined ? undefined : String(params.offset),
          },
        }),
      create: (workspaceId: string, body: WorkspaceTaskCreateRequest) =>
        request<WorkspaceTaskOut>(`/v1/workspaces/${workspaceId}/tasks`, {
          method: "POST",
          body,
        }),
      get: (workspaceId: string, taskId: string) =>
        request<WorkspaceTaskOut>(`/v1/workspaces/${workspaceId}/tasks/${taskId}`),
      patch: (workspaceId: string, taskId: string, body: WorkspaceTaskPatchRequest) =>
        request<WorkspaceTaskOut>(`/v1/workspaces/${workspaceId}/tasks/${taskId}`, {
          method: "PATCH",
          body,
        }),
      remove: (workspaceId: string, taskId: string) =>
        request<void>(`/v1/workspaces/${workspaceId}/tasks/${taskId}`, { method: "DELETE" }),
      accept: (workspaceId: string, taskId: string) =>
        request<WorkspaceTaskOut>(`/v1/workspaces/${workspaceId}/tasks/${taskId}/accept`, {
          method: "POST",
        }),
      decline: (workspaceId: string, taskId: string) =>
        request<WorkspaceTaskOut>(`/v1/workspaces/${workspaceId}/tasks/${taskId}/decline`, {
          method: "POST",
        }),
    },
    roadmaps: {
      list: (workspaceId: string, params: { limit?: number; offset?: number } = {}) =>
        request<RelationshipRoadmapOut[]>(`/v1/workspaces/${workspaceId}/roadmaps`, {
          query: {
            limit: params.limit === undefined ? undefined : String(params.limit),
            offset: params.offset === undefined ? undefined : String(params.offset),
          },
        }),
      create: (workspaceId: string, body: RelationshipRoadmapCreateRequest) =>
        request<RelationshipRoadmapOut>(`/v1/workspaces/${workspaceId}/roadmaps`, {
          method: "POST",
          body,
        }),
      get: (workspaceId: string, roadmapId: string) =>
        request<RelationshipRoadmapOut>(`/v1/workspaces/${workspaceId}/roadmaps/${roadmapId}`),
      patch: (workspaceId: string, roadmapId: string, body: RelationshipRoadmapPatchRequest) =>
        request<RelationshipRoadmapOut>(`/v1/workspaces/${workspaceId}/roadmaps/${roadmapId}`, {
          method: "PATCH",
          body,
        }),
      remove: (workspaceId: string, roadmapId: string) =>
        request<void>(`/v1/workspaces/${workspaceId}/roadmaps/${roadmapId}`, {
          method: "DELETE",
        }),
      milestones: {
        list: (workspaceId: string, roadmapId: string, milestoneType?: MilestoneType) =>
          request<RoadmapMilestoneOut[]>(
            `/v1/workspaces/${workspaceId}/roadmaps/${roadmapId}/milestones`,
            { query: { milestone_type: milestoneType } },
          ),
        create: (workspaceId: string, roadmapId: string, body: RoadmapMilestoneCreateRequest) =>
          request<RoadmapMilestoneOut>(
            `/v1/workspaces/${workspaceId}/roadmaps/${roadmapId}/milestones`,
            { method: "POST", body },
          ),
        get: (workspaceId: string, roadmapId: string, milestoneId: string) =>
          request<RoadmapMilestoneOut>(
            `/v1/workspaces/${workspaceId}/roadmaps/${roadmapId}/milestones/${milestoneId}`,
          ),
        patch: (
          workspaceId: string,
          roadmapId: string,
          milestoneId: string,
          body: RoadmapMilestonePatchRequest,
        ) =>
          request<RoadmapMilestoneOut>(
            `/v1/workspaces/${workspaceId}/roadmaps/${roadmapId}/milestones/${milestoneId}`,
            { method: "PATCH", body },
          ),
        remove: (workspaceId: string, roadmapId: string, milestoneId: string) =>
          request<void>(
            `/v1/workspaces/${workspaceId}/roadmaps/${roadmapId}/milestones/${milestoneId}`,
            { method: "DELETE" },
          ),
      },
    },
    copilot: {
      threads: {
        list: (workspaceId: string) =>
          request<ChatThreadOut[]>(`/v1/workspaces/${workspaceId}/copilot/threads`),
        create: (workspaceId: string, body: ThreadCreateRequest) =>
          request<ChatThreadOut>(`/v1/workspaces/${workspaceId}/copilot/threads`, {
            method: "POST",
            body,
          }),
        get: (workspaceId: string, threadId: string) =>
          request<ChatThreadOut>(`/v1/workspaces/${workspaceId}/copilot/threads/${threadId}`),
        archive: (workspaceId: string, threadId: string) =>
          request<ChatThreadOut>(
            `/v1/workspaces/${workspaceId}/copilot/threads/${threadId}/archive`,
            { method: "POST" },
          ),
        messages: {
          list: (
            workspaceId: string,
            threadId: string,
            params: { limit?: number; offset?: number } = {},
          ) =>
            request<ChatMessageOut[]>(
              `/v1/workspaces/${workspaceId}/copilot/threads/${threadId}/messages`,
              {
                query: {
                  limit: params.limit === undefined ? undefined : String(params.limit),
                  offset: params.offset === undefined ? undefined : String(params.offset),
                },
              },
            ),
          post: (workspaceId: string, threadId: string, body: MessageCreateRequest) =>
            request<MessagePairOut>(
              `/v1/workspaces/${workspaceId}/copilot/threads/${threadId}/messages`,
              { method: "POST", body },
            ),
        },
      },
    },
  },
  /** /v1/people/{person_id}/personal-tasks -- person-scoped, distinct from
   *  api.workspaces.tasks (workspace-scoped). */
  personalTasks: {
    list: (
      personId: string,
      params: { status?: PersonalTaskStatus; limit?: number; offset?: number } = {},
    ) =>
      request<PersonalTaskOut[]>(`/v1/people/${personId}/personal-tasks`, {
        query: {
          status: params.status,
          limit: params.limit === undefined ? undefined : String(params.limit),
          offset: params.offset === undefined ? undefined : String(params.offset),
        },
      }),
    create: (personId: string, body: PersonalTaskCreateRequest) =>
      request<PersonalTaskOut>(`/v1/people/${personId}/personal-tasks`, {
        method: "POST",
        body,
      }),
    get: (taskId: string) => request<PersonalTaskOut>(`/v1/personal-tasks/${taskId}`),
    patch: (taskId: string, body: PersonalTaskPatchRequest) =>
      request<PersonalTaskOut>(`/v1/personal-tasks/${taskId}`, { method: "PATCH", body }),
    remove: (taskId: string) =>
      request<void>(`/v1/personal-tasks/${taskId}`, { method: "DELETE" }),
  },
  entitlements: {
    get: () => request<EntitlementSetOut>("/v1/me/entitlements"),
  },
  myWorkspace: {
    get: (personId: string) =>
      request<MyWorkspaceOverviewOut>("/v1/me/workspace", { query: { person_id: personId } }),
  },
};
