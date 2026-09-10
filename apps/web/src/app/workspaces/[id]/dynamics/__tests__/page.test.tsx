import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import WorkspaceDynamicsPage from "@/app/workspaces/[id]/dynamics/page";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError, type WorkspaceOverviewOut } from "@/api/client";
import { relationshipAnalysisPending } from "@/fixtures/analysis";

const useParams = vi.fn();
vi.mock("next/navigation", () => ({
  useParams: () => useParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/workspaces/ws-1/dynamics",
}));

vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    api: {
      workspaces: {
        get: vi.fn(),
        list: vi.fn(),
        relationshipAnalysis: { getLatest: vi.fn(), get: vi.fn(), create: vi.fn() },
        shadowDynamics: { getLatest: vi.fn(), get: vi.fn(), create: vi.fn() },
      },
      connections: { list: vi.fn() },
      analysisJobs: { get: vi.fn() },
    },
  };
});

function overview(over: Partial<WorkspaceOverviewOut> = {}): WorkspaceOverviewOut {
  return {
    workspace: {
      id: "ws-1",
      connection_id: "conn-1",
      status: "ACTIVE",
      relationship_type: "PARTNER",
      created_at: "2026-01-01T00:00:00Z",
      dissolved_at: null,
    },
    dual_profile: [
      { user_id: "me", display_name: "Lukas", self_person: { id: "p1", display_name: "Lukas" }, core_numbers: null },
      { user_id: "them", display_name: "Ada", self_person: null, core_numbers: null },
    ],
    ...over,
  } as WorkspaceOverviewOut;
}

const notFound = () => new ApiError("Not found.", "NOT_FOUND", 404);

function renderPage() {
  return render(
    <LocaleProvider>
      <WorkspaceDynamicsPage />
    </LocaleProvider>,
  );
}

beforeEach(() => {
  useParams.mockReturnValue({ id: "ws-1" });
  vi.mocked(useAuth).mockReturnValue({
    status: "authenticated",
    user: { id: "me", email: "me@example.com", role: "USER", is_active: true },
    error: null,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
  } as ReturnType<typeof useAuth>);
  vi.mocked(api.workspaces.get).mockReset().mockResolvedValue(overview());
  vi.mocked(api.workspaces.list).mockReset().mockResolvedValue([]);
  vi.mocked(api.connections.list).mockReset().mockResolvedValue([]);
  const rel = api.workspaces.relationshipAnalysis as unknown as { getLatest: ReturnType<typeof vi.fn>; get: ReturnType<typeof vi.fn>; create: ReturnType<typeof vi.fn> };
  const shadow = api.workspaces.shadowDynamics as unknown as { getLatest: ReturnType<typeof vi.fn>; get: ReturnType<typeof vi.fn>; create: ReturnType<typeof vi.fn> };
  rel.getLatest.mockReset().mockRejectedValue(notFound());
  rel.create.mockReset().mockResolvedValue(relationshipAnalysisPending);
  rel.get.mockReset();
  shadow.getLatest.mockReset().mockRejectedValue(notFound());
  shadow.create.mockReset().mockResolvedValue({ ...relationshipAnalysisPending, id: "shadow-analysis-1", job_id: "shadow-job-1" });
  shadow.get.mockReset();
  (api.analysisJobs.get as unknown as ReturnType<typeof vi.fn>)
    .mockReset()
    .mockResolvedValue({
      id: "rel-job-1",
      workspace_id: "ws-1",
      analysis_type: "RELATIONSHIP_INTERPRETATION",
      status: "GENERATING",
      progress: 80,
      error_code: null,
      attempt_count: 1,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });
});

describe("WorkspaceDynamicsPage", () => {
  it("renders both analysis sections", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "Beziehungsanalyse" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Schattendynamik" })).toBeInTheDocument();
  });

  it("shows a full-width gate and no sections for a DISSOLVED workspace", async () => {
    vi.mocked(api.workspaces.get).mockResolvedValue(
      overview({
        workspace: {
          id: "ws-1",
          connection_id: "conn-1",
          status: "DISSOLVED",
          relationship_type: "PARTNER",
          created_at: "2026-01-01T00:00:00Z",
          dissolved_at: "2026-02-01T00:00:00Z",
        },
      }),
    );
    renderPage();
    expect(await screen.findByText("Workspace aufgelöst")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Beziehungsanalyse" })).not.toBeInTheDocument();
  });

  it("starts a generation when the section's launch button is clicked", async () => {
    renderPage();
    const launch = await screen.findByRole("button", { name: "Beziehungsanalyse starten" });
    fireEvent.click(launch);
    const rel = api.workspaces.relationshipAnalysis as unknown as { getLatest: ReturnType<typeof vi.fn>; get: ReturnType<typeof vi.fn>; create: ReturnType<typeof vi.fn> };
    await vi.waitFor(() => expect(rel.create).toHaveBeenCalledWith("ws-1", expect.any(String)));
  });
});
