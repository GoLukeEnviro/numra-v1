import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, type WorkspaceOverviewOut, type WorkspaceTaskOut } from "@/api/client";
import { WorkspaceTasksContent } from "@/components/workspaces/tasks/workspace-tasks-content";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

vi.mock("next/navigation", () => ({ usePathname: () => "/workspaces/ws-1/tasks", useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));
vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));
vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return { ...actual, api: { ...actual.api, workspaces: { ...actual.api.workspaces, list: vi.fn(), tasks: { ...actual.api.workspaces.tasks, create: vi.fn(), accept: vi.fn(), decline: vi.fn(), patch: vi.fn() } }, connections: { ...actual.api.connections, list: vi.fn() } } };
});

const overview = (status: "ACTIVE" | "DISSOLVED" = "ACTIVE") => ({
  workspace: { id: "ws-1", connection_id: "conn-1", status, relationship_type: "PARTNER", created_at: "2026-01-01T00:00:00Z", dissolved_at: status === "DISSOLVED" ? "2026-09-01T00:00:00Z" : null },
  dual_profile: [{ user_id: "me", display_name: "Lukas", self_person: null, core_numbers: null }, { user_id: "them", display_name: "Ada", self_person: null, core_numbers: null }],
}) as WorkspaceOverviewOut;

const task = (overrides: Partial<WorkspaceTaskOut> = {}): WorkspaceTaskOut => ({
  id: "task-1", workspace_id: "ws-1", task_type: "JOINT_SHARED", status: "ACTIVE", proposer_user_id: "me", recipient_user_id: null, title: "Zusammen kochen", description: null, due_date: null, completed_at: null, source_analysis_id: null, prompt_version: null, knowledge_version: null, roadmap_milestone_id: null, created_at: "2026-09-10T12:00:00Z", updated_at: "2026-09-10T12:00:00Z", ...overrides,
});

function renderTasks(tasks: WorkspaceTaskOut[], status: "ACTIVE" | "DISSOLVED" = "ACTIVE") {
  return render(<LocaleProvider><WorkspaceTasksContent workspaceId="ws-1" overview={overview(status)} tasks={tasks} /></LocaleProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(useAuth).mockReturnValue({ status: "authenticated", user: { id: "me" }, error: null } as ReturnType<typeof useAuth>);
  vi.mocked(api.workspaces.list).mockResolvedValue([]);
  vi.mocked(api.connections.list).mockResolvedValue([]);
});

describe("WorkspaceTasksContent", () => {
  it("creates a partner proposal and explains that acceptance is required", async () => {
    vi.mocked(api.workspaces.tasks.create).mockResolvedValue(task({ task_type: "FOR_PARTNER_PROPOSED", status: "PROPOSED", recipient_user_id: "them", title: "Mehr Zeit einplanen" }));
    renderTasks([]);
    fireEvent.click(screen.getByRole("button", { name: "Aufgabe anlegen" }));
    fireEvent.change(screen.getByLabelText("Aufgabentyp"), { target: { value: "FOR_PARTNER_PROPOSED" } });
    fireEvent.change(screen.getByLabelText("Titel"), { target: { value: "Mehr Zeit einplanen" } });
    expect(screen.getByText(/ausdrücklich annehmen/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Anlegen" }));
    await waitFor(() => expect(api.workspaces.tasks.create).toHaveBeenCalledWith("ws-1", { task_type: "FOR_PARTNER_PROPOSED", title: "Mehr Zeit einplanen", description: null, due_date: null }));
    expect(await screen.findByText("Mehr Zeit einplanen")).toBeInTheDocument();
  });

  it("lets only the recipient accept or decline a proposed partner task", async () => {
    vi.mocked(api.workspaces.tasks.accept).mockResolvedValue(task());
    const incoming = task({ task_type: "FOR_PARTNER_PROPOSED", status: "PROPOSED", proposer_user_id: "them", recipient_user_id: "me" });
    const first = renderTasks([incoming]);
    fireEvent.click(screen.getByRole("button", { name: "Annehmen" }));
    await waitFor(() => expect(api.workspaces.tasks.accept).toHaveBeenCalledWith("ws-1", "task-1"));

    first.unmount();
    renderTasks([task({ id: "task-2", task_type: "FOR_PARTNER_PROPOSED", status: "PROPOSED", proposer_user_id: "me", recipient_user_id: "them" })]);
    expect(screen.getByText("Wartet auf Annahme")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Annehmen" })).not.toBeInTheDocument();
  });

  it("completes active shared work through the server transition", async () => {
    vi.mocked(api.workspaces.tasks.patch).mockResolvedValue(task({ status: "COMPLETED" }));
    renderTasks([task()]);
    fireEvent.click(screen.getByRole("button", { name: "Als erledigt markieren" }));
    await waitFor(() => expect(api.workspaces.tasks.patch).toHaveBeenCalledWith("ws-1", "task-1", { status: "COMPLETED" }));
  });

  it("renders dissolved workspaces without mutation controls", () => {
    renderTasks([task({ status: "COMPLETED" }), task({ id: "archived", status: "ARCHIVED", title: "Archivierte Aufgabe" })], "DISSOLVED");
    expect(screen.getByRole("heading", { name: "Historische Ansicht" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Aufgabe anlegen" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Als erledigt markieren" })).not.toBeInTheDocument();
    expect(screen.getByText("Zusammen kochen")).toBeInTheDocument();
    expect(screen.getByText("Archivierte Aufgabe")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Archiv" })).toBeInTheDocument();
  });

  it("keeps an open creation draft while another task changes", async () => {
    vi.mocked(api.workspaces.tasks.patch).mockResolvedValue(task({ status: "COMPLETED" }));
    renderTasks([task()]);
    fireEvent.click(screen.getByRole("button", { name: "Aufgabe anlegen" }));
    fireEvent.change(screen.getByLabelText("Titel"), { target: { value: "Mein offener Entwurf" } });
    fireEvent.click(screen.getByRole("button", { name: "Als erledigt markieren" }));
    await waitFor(() => expect(api.workspaces.tasks.patch).toHaveBeenCalled());
    expect(screen.getByLabelText("Titel")).toHaveValue("Mein offener Entwurf");
  });
});
