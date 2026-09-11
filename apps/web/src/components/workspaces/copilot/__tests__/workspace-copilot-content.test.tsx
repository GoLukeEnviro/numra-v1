import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  api,
  type ChatMessageOut,
  type ChatThreadOut,
  type WorkspaceOverviewOut,
} from "@/api/client";
import { WorkspaceCopilotContent } from "@/components/workspaces/copilot/workspace-copilot-content";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

vi.mock("next/navigation", () => ({
  usePathname: () => "/workspaces/ws-1/copilot",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));
vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));
vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    api: {
      ...actual.api,
      workspaces: {
        ...actual.api.workspaces,
        list: vi.fn(),
        copilot: {
          threads: {
            list: vi.fn(),
            create: vi.fn(),
            get: vi.fn(),
            archive: vi.fn(),
            messages: { list: vi.fn(), post: vi.fn() },
          },
        },
      },
      connections: { ...actual.api.connections, list: vi.fn() },
    },
  };
});

const overview = {
  workspace: {
    id: "ws-1",
    connection_id: "conn-1",
    status: "ACTIVE",
    relationship_type: "PARTNER",
    created_at: "2026-01-01T00:00:00Z",
    dissolved_at: null,
  },
  dual_profile: [
    { user_id: "me", display_name: "Lukas", self_person: null, core_numbers: null },
    { user_id: "them", display_name: "Ada", self_person: null, core_numbers: null },
  ],
} as WorkspaceOverviewOut;

function thread(scope: "RELATIONSHIP_SHARED" | "RELATIONSHIP_PRIVATE", id = "thread-shared"): ChatThreadOut {
  return {
    id,
    workspace_id: "ws-1",
    owner_user_id: scope === "RELATIONSHIP_PRIVATE" ? "me" : null,
    scope,
    context_version: 1,
    created_at: "2026-09-11T12:00:00Z",
    archived_at: null,
  };
}

function message(overrides: Partial<ChatMessageOut> = {}): ChatMessageOut {
  return {
    id: "message-1",
    thread_id: "thread-shared",
    role: "ASSISTANT",
    status: "COMPLETE",
    author_user_id: null,
    content: "Eure Check-ins zeigen einen stabilen Austausch.",
    basis_type: "OBSERVED_WORKSPACE_DATA",
    prompt_version: "numra-copilot-v1",
    knowledge_version: "copilot-shared-v1",
    context_snapshot_id: "snapshot-1",
    model_provider: "test",
    model_name: "deterministic-test",
    error_code: null,
    created_at: "2026-09-11T12:01:00Z",
    ...overrides,
  };
}

function renderContent(value: WorkspaceOverviewOut = overview) {
  return render(
    <LocaleProvider>
      <WorkspaceCopilotContent workspaceId="ws-1" overview={value} />
    </LocaleProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(useAuth).mockReturnValue({
    status: "authenticated",
    user: { id: "me" },
    error: null,
  } as ReturnType<typeof useAuth>);
  vi.mocked(api.workspaces.list).mockResolvedValue([]);
  vi.mocked(api.connections.list).mockResolvedValue([]);
  vi.mocked(api.workspaces.copilot.threads.list).mockResolvedValue([thread("RELATIONSHIP_SHARED")]);
  vi.mocked(api.workspaces.copilot.threads.messages.list).mockResolvedValue([message()]);
});

describe("WorkspaceCopilotContent", () => {
  it("loads the shared thread by default and labels every assistant answer by its evidence basis", async () => {
    renderContent();

    expect(await screen.findByText("Eure Check-ins zeigen einen stabilen Austausch.")).toBeInTheDocument();
    expect(screen.getByText("Beobachtete Workspace-Daten")).toBeInTheDocument();
    expect(screen.getByText(/für euch beide sichtbar/)).toBeInTheDocument();
    expect(api.workspaces.copilot.threads.messages.list).toHaveBeenCalledWith(
      "ws-1",
      "thread-shared",
      { limit: 100, offset: 0 },
    );
  });

  it("creates an isolated private thread on demand and clears the shared messages immediately", async () => {
    vi.mocked(api.workspaces.copilot.threads.create).mockResolvedValue(
      thread("RELATIONSHIP_PRIVATE", "thread-private"),
    );
    vi.mocked(api.workspaces.copilot.threads.messages.list).mockResolvedValueOnce([message()]).mockResolvedValueOnce([]);
    renderContent();
    await screen.findByText("Eure Check-ins zeigen einen stabilen Austausch.");

    fireEvent.click(screen.getByRole("button", { name: "Privat" }));

    expect(screen.queryByText("Eure Check-ins zeigen einen stabilen Austausch.")).not.toBeInTheDocument();
    expect(await screen.findByText(/Dein Partner sieht weder deine Fragen noch die Antworten/)).toBeInTheDocument();
    await waitFor(() =>
      expect(api.workspaces.copilot.threads.create).toHaveBeenCalledWith("ws-1", {
        scope: "RELATIONSHIP_PRIVATE",
      }),
    );
    expect(api.workspaces.copilot.threads.messages.list).toHaveBeenLastCalledWith(
      "ws-1",
      "thread-private",
      { limit: 100, offset: 0 },
    );
  });

  it("trims and posts a message once, then renders insufficient evidence as a valid answer", async () => {
    let resolvePost!: (value: Awaited<ReturnType<typeof api.workspaces.copilot.threads.messages.post>>) => void;
    vi.mocked(api.workspaces.copilot.threads.messages.post).mockReturnValue(
      new Promise((resolve) => { resolvePost = resolve; }),
    );
    renderContent();
    await screen.findByText("Eure Check-ins zeigen einen stabilen Austausch.");

    fireEvent.change(screen.getByLabelText("Nachricht"), { target: { value: "  Was fällt auf?  " } });
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));
    expect(screen.getByRole("button", { name: "Wird gesendet …" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Wird gesendet …" }));

    resolvePost({
      user_message: message({ id: "user-2", role: "USER", author_user_id: "me", content: "Was fällt auf?", basis_type: null }),
      assistant_message: message({ id: "assistant-2", content: "Dafür liegen noch nicht genügend Daten vor.", basis_type: "INSUFFICIENT_EVIDENCE" }),
    });

    expect(await screen.findByText("Dafür liegen noch nicht genügend Daten vor.")).toBeInTheDocument();
    expect(screen.getByText("Noch keine ausreichende Datengrundlage")).toBeInTheDocument();
    expect(api.workspaces.copilot.threads.messages.post).toHaveBeenCalledTimes(1);
    expect(api.workspaces.copilot.threads.messages.post).toHaveBeenCalledWith(
      "ws-1",
      "thread-shared",
      { content: "Was fällt auf?" },
    );
  });

  it("rejects whitespace, recovers from send errors, and allows retry", async () => {
    vi.mocked(api.workspaces.copilot.threads.messages.post)
      .mockRejectedValueOnce(new Error("Provider unavailable"))
      .mockResolvedValueOnce({
        user_message: message({ id: "user-3", role: "USER", content: "Noch einmal", basis_type: null }),
        assistant_message: message({ id: "assistant-3", content: "Jetzt klappt es.", basis_type: "MIXED" }),
      });
    renderContent();
    await screen.findByText("Eure Check-ins zeigen einen stabilen Austausch.");

    const input = screen.getByLabelText("Nachricht");
    fireEvent.change(input, { target: { value: "   " } });
    expect(screen.getByRole("button", { name: "Senden" })).toBeDisabled();

    fireEvent.change(input, { target: { value: "Noch einmal" } });
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Provider unavailable");
    expect(screen.getByRole("button", { name: "Senden" })).toBeEnabled();

    fireEvent.click(screen.getByRole("button", { name: "Senden" }));
    expect(await screen.findByText("Jetzt klappt es.")).toBeInTheDocument();
    expect(screen.getByText("Numerologie und Workspace-Daten")).toBeInTheDocument();
  });

  it("archives the active thread and creates a fresh empty thread", async () => {
    vi.mocked(api.workspaces.copilot.threads.archive).mockResolvedValue({
      ...thread("RELATIONSHIP_SHARED"),
      archived_at: "2026-09-11T13:00:00Z",
    });
    vi.mocked(api.workspaces.copilot.threads.create).mockResolvedValue(
      thread("RELATIONSHIP_SHARED", "thread-new"),
    );
    vi.mocked(api.workspaces.copilot.threads.messages.list).mockResolvedValueOnce([message()]).mockResolvedValueOnce([]);
    renderContent();
    await screen.findByText("Eure Check-ins zeigen einen stabilen Austausch.");

    fireEvent.click(screen.getByRole("button", { name: "Gespräch archivieren" }));

    await waitFor(() => expect(api.workspaces.copilot.threads.archive).toHaveBeenCalledWith("ws-1", "thread-shared"));
    await waitFor(() => expect(api.workspaces.copilot.threads.create).toHaveBeenCalledWith("ws-1", { scope: "RELATIONSHIP_SHARED" }));
    expect(await screen.findByText("Noch keine Nachrichten in diesem Gespräch.")).toBeInTheDocument();
  });

  it("discards a delayed shared reply after switching to the private mode", async () => {
    let resolvePost!: (value: Awaited<ReturnType<typeof api.workspaces.copilot.threads.messages.post>>) => void;
    vi.mocked(api.workspaces.copilot.threads.messages.post).mockReturnValue(new Promise((resolve) => { resolvePost = resolve; }));
    vi.mocked(api.workspaces.copilot.threads.create).mockResolvedValue(thread("RELATIONSHIP_PRIVATE", "thread-private"));
    vi.mocked(api.workspaces.copilot.threads.messages.list).mockResolvedValueOnce([message()]).mockResolvedValueOnce([]);
    renderContent();
    await screen.findByText("Eure Check-ins zeigen einen stabilen Austausch.");
    fireEvent.change(screen.getByLabelText("Nachricht"), { target: { value: "Shared pending" } });
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));
    fireEvent.click(screen.getByRole("button", { name: "Privat" }));
    await screen.findByText("Noch keine Nachrichten in diesem Gespräch.");
    expect(screen.getByLabelText("Nachricht")).toBeEnabled();

    resolvePost({
      user_message: message({ id: "late-user", role: "USER", content: "Shared pending", basis_type: null }),
      assistant_message: message({ id: "late-assistant", content: "Nur im gemeinsamen Verlauf", basis_type: "MIXED" }),
    });

    await waitFor(() => expect(api.workspaces.copilot.threads.messages.post).toHaveBeenCalledTimes(1));
    expect(screen.queryByText("Nur im gemeinsamen Verlauf")).not.toBeInTheDocument();
  });

  it("does not let a delayed shared archive replace the selected private thread", async () => {
    let resolveArchive!: (value: ChatThreadOut) => void;
    vi.mocked(api.workspaces.copilot.threads.archive).mockReturnValue(new Promise((resolve) => { resolveArchive = resolve; }));
    vi.mocked(api.workspaces.copilot.threads.create).mockResolvedValue(thread("RELATIONSHIP_PRIVATE", "thread-private"));
    vi.mocked(api.workspaces.copilot.threads.messages.list).mockResolvedValueOnce([message()]).mockResolvedValueOnce([]);
    renderContent();
    await screen.findByText("Eure Check-ins zeigen einen stabilen Austausch.");

    fireEvent.click(screen.getByRole("button", { name: "Gespräch archivieren" }));
    fireEvent.click(screen.getByRole("button", { name: "Privat" }));
    expect(await screen.findByText(/Dein Partner sieht weder deine Fragen noch die Antworten/)).toBeInTheDocument();
    await screen.findByText("Noch keine Nachrichten in diesem Gespräch.");

    resolveArchive({ ...thread("RELATIONSHIP_SHARED"), archived_at: "2026-09-11T13:00:00Z" });

    await waitFor(() => expect(api.workspaces.copilot.threads.archive).toHaveBeenCalledTimes(1));
    expect(api.workspaces.copilot.threads.create).toHaveBeenCalledTimes(1);
    expect(api.workspaces.copilot.threads.create).toHaveBeenCalledWith("ws-1", { scope: "RELATIONSHIP_PRIVATE" });
    expect(screen.getByText("Noch keine Nachrichten in diesem Gespräch.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Gespräch archivieren" })).toBeEnabled();
  });

  it("loads every message page so recent history is not truncated", async () => {
    const firstPage = Array.from({ length: 100 }, (_, index) => message({ id: `message-${index}` }));
    const recent = message({ id: "message-100", content: "Neueste Nachricht" });
    vi.mocked(api.workspaces.copilot.threads.messages.list)
      .mockResolvedValueOnce(firstPage)
      .mockResolvedValueOnce([recent]);

    renderContent();

    expect(await screen.findByText("Neueste Nachricht")).toBeInTheDocument();
    expect(api.workspaces.copilot.threads.messages.list).toHaveBeenNthCalledWith(
      2,
      "ws-1",
      "thread-shared",
      { limit: 100, offset: 100 },
    );
  });

  it("keeps dissolved workspaces read-only while showing retained history", async () => {
    renderContent({
      ...overview,
      workspace: { ...overview.workspace, status: "DISSOLVED", dissolved_at: "2026-09-11T14:00:00Z" },
    });

    expect(await screen.findByText("Eure Check-ins zeigen einen stabilen Austausch.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Nachricht")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Gespräch archivieren" })).not.toBeInTheDocument();
    expect(api.workspaces.copilot.threads.create).not.toHaveBeenCalled();
  });

  it("derives the counterpart name from the authenticated user instead of member ordering", async () => {
    renderContent({ ...overview, dual_profile: [...overview.dual_profile].reverse() });
    expect(await screen.findByRole("heading", { name: "Ada" })).toBeInTheDocument();
  });
});
