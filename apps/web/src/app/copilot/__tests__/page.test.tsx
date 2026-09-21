import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CopilotPage from "@/app/copilot/page";
import {
  api,
  ApiError,
  type ChatMessageOut,
  type ChatThreadOut,
  type UserConnectionOut,
  type WorkspaceSummaryOut,
} from "@/api/client";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

vi.mock("next/navigation", () => ({
  usePathname: () => "/copilot",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));
vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));
vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    api: {
      ...actual.api,
      me: {
        ...actual.api.me,
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

const workspace = {
  id: "ws-1",
  connection_id: "conn-1",
  status: "ACTIVE",
  relationship_type: "PARTNER",
  created_at: "2026-01-01T00:00:00Z",
  dissolved_at: null,
} as WorkspaceSummaryOut;

const connection = {
  id: "conn-1",
  counterpart_user_id: "them",
  counterpart_display_name: "Ada Lovelace",
  status: "ACTIVE",
  created_at: "2026-01-01T00:00:00Z",
  dissolved_at: null,
} as UserConnectionOut;

function personalThread(id = "thread-personal"): ChatThreadOut {
  return {
    id,
    workspace_id: null,
    owner_user_id: "me",
    scope: "PERSONAL_PRIVATE",
    context_version: 1,
    created_at: "2026-09-11T12:00:00Z",
    archived_at: null,
  };
}

function personalMessage(overrides: Partial<ChatMessageOut> = {}): ChatMessageOut {
  return {
    id: "message-1",
    thread_id: "thread-personal",
    role: "ASSISTANT",
    status: "COMPLETE",
    author_user_id: null,
    content: "Dein Profil zeigt eine klare 7.",
    basis_type: "NUMEROLOGY_MODEL",
    prompt_version: "numra-copilot-v1",
    knowledge_version: "copilot-personal-v1",
    context_snapshot_id: "snapshot-1",
    model_provider: "test",
    model_name: "deterministic-test",
    error_code: null,
    created_at: "2026-09-11T12:01:00Z",
    ...overrides,
  };
}

function renderPage() {
  return render(<LocaleProvider><CopilotPage /></LocaleProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(useAuth).mockReturnValue({ status: "authenticated", user: { id: "me" }, error: null } as ReturnType<typeof useAuth>);
  vi.mocked(api.workspaces.list).mockResolvedValue([]);
  vi.mocked(api.connections.list).mockResolvedValue([]);
  vi.mocked(api.me.copilot.threads.list).mockResolvedValue([personalThread()]);
  vi.mocked(api.me.copilot.threads.messages.list).mockResolvedValue([personalMessage()]);
});

describe("CopilotPage", () => {
  it("leads with the personal copilot and renders its own thread without any workspace", async () => {
    vi.mocked(api.me.copilot.threads.list).mockResolvedValue([]);
    vi.mocked(api.me.copilot.threads.create).mockResolvedValue(personalThread());
    vi.mocked(api.me.copilot.threads.messages.list).mockResolvedValue([]);
    renderPage();

    expect(await screen.findByRole("heading", { name: "Persönliches Gespräch" })).toBeInTheDocument();
    await waitFor(() => expect(api.me.copilot.threads.create).toHaveBeenCalledTimes(1));
    expect(api.me.copilot.threads.messages.list).toHaveBeenCalledWith("thread-personal", {
      limit: 100,
      offset: 0,
    });
    // The personal surface must never borrow a workspace-bound call.
    expect(api.workspaces.copilot.threads.list).not.toHaveBeenCalled();
  });

  it("does not create a second thread when the caller already has one", async () => {
    renderPage();

    expect(await screen.findByText("Dein Profil zeigt eine klare 7.")).toBeInTheDocument();
    expect(api.me.copilot.threads.create).not.toHaveBeenCalled();
  });

  it("links active relationship workspaces to their copilot below the personal surface", async () => {
    vi.mocked(api.workspaces.list).mockResolvedValue([workspace]);
    vi.mocked(api.connections.list).mockResolvedValue([connection]);
    renderPage();

    expect(await screen.findByRole("link", { name: /Ada Lovelace/ })).toHaveAttribute("href", "/workspaces/ws-1/copilot");
  });

  it("keeps the relationship empty state while the personal copilot stays usable", async () => {
    renderPage();

    expect(await screen.findByText("Noch kein Beziehungs-Copilot verfügbar")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Verbindungen ansehen" })).toHaveAttribute("href", "/connections");
    expect(screen.getByRole("heading", { name: "Persönliches Gespräch" })).toBeInTheDocument();
  });

  it("renders the calm phase-disabled state instead of an error when the copilot flag is off", async () => {
    vi.mocked(api.me.copilot.threads.list).mockRejectedValue(
      new ApiError("phase disabled", "V2_PHASE_DISABLED", 403),
    );
    renderPage();

    expect(await screen.findByText("Copilot noch nicht verfügbar")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("surfaces a real personal-copilot failure as a retryable error, not as a phase gate", async () => {
    vi.mocked(api.me.copilot.threads.list).mockRejectedValue(
      new ApiError("boom", "INTERNAL_ERROR", 500),
    );
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });

  it("sends a personal message and renders the assistant basis label", async () => {
    vi.mocked(api.me.copilot.threads.messages.post).mockResolvedValue({
      user_message: personalMessage({ id: "user-2", role: "USER", author_user_id: "me", content: "Was fällt auf?", basis_type: null }),
      assistant_message: personalMessage({ id: "assistant-2", content: "Dafür reicht es noch nicht.", basis_type: "INSUFFICIENT_EVIDENCE" }),
    });
    renderPage();
    await screen.findByText("Dein Profil zeigt eine klare 7.");

    fireEvent.change(screen.getByLabelText("Nachricht"), { target: { value: "  Was fällt auf?  " } });
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));

    expect(await screen.findByText("Dafür reicht es noch nicht.")).toBeInTheDocument();
    expect(screen.getByText("Noch keine ausreichende Datengrundlage")).toBeInTheDocument();
    expect(api.me.copilot.threads.messages.post).toHaveBeenCalledWith("thread-personal", {
      content: "Was fällt auf?",
    });
  });

  it("archives the personal thread and starts a fresh empty one", async () => {
    vi.mocked(api.me.copilot.threads.archive).mockResolvedValue({ ...personalThread(), archived_at: "2026-09-11T13:00:00Z" });
    vi.mocked(api.me.copilot.threads.create).mockResolvedValue(personalThread("thread-new"));
    vi.mocked(api.me.copilot.threads.messages.list).mockResolvedValueOnce([personalMessage()]).mockResolvedValueOnce([]);
    renderPage();
    await screen.findByText("Dein Profil zeigt eine klare 7.");

    fireEvent.click(screen.getByRole("button", { name: "Gespräch archivieren" }));

    await waitFor(() => expect(api.me.copilot.threads.archive).toHaveBeenCalledWith("thread-personal"));
    await waitFor(() => expect(api.me.copilot.threads.create).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Noch keine Nachrichten in diesem Gespräch.")).toBeInTheDocument();
  });

  it("does not render the relationship workspace list inside the personal surface", async () => {
    renderPage();

    await screen.findByText("Dein Profil zeigt eine klare 7.");
    const personal = screen.getByRole("region", { name: "Persönliches Gespräch" });
    expect(personal).not.toHaveTextContent("Beziehungs-Copiloten");
  });
});
