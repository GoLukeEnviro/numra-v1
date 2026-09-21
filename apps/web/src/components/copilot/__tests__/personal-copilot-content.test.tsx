import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PersonalCopilotContent } from "@/components/copilot/personal-copilot-content";
import { api, ApiError, type ChatMessageOut, type ChatThreadOut } from "@/api/client";
import type { PhaseErrorCode } from "@/components/ui/states";
import { LocaleProvider } from "@/i18n/context";

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
      // Spied so the "no workspace-bound call" assertion can actually fail: a real
      // function is not a spy, and `not.toHaveBeenCalled()` on one throws instead of
      // proving anything.
      workspaces: {
        ...actual.api.workspaces,
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
    },
  };
});

function thread(id = "thread-personal"): ChatThreadOut {
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

function message(overrides: Partial<ChatMessageOut> = {}): ChatMessageOut {
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

function renderContent(onPhaseDisabled?: (code: PhaseErrorCode) => void) {
  return render(
    <LocaleProvider>
      <PersonalCopilotContent onPhaseDisabled={onPhaseDisabled} />
    </LocaleProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.me.copilot.threads.list).mockResolvedValue([thread()]);
  vi.mocked(api.me.copilot.threads.messages.list).mockResolvedValue([message()]);
});

describe("PersonalCopilotContent", () => {
  it("loads the caller's own personal thread and labels the assistant basis", async () => {
    renderContent();

    expect(await screen.findByText("Dein Profil zeigt eine klare 7.")).toBeInTheDocument();
    expect(screen.getByText("Numerologisches Modell")).toBeInTheDocument();
    expect(api.me.copilot.threads.messages.list).toHaveBeenCalledWith("thread-personal", {
      limit: 100,
      offset: 0,
    });
  });

  it("never falls back to workspace-bound copilot calls", async () => {
    renderContent();
    await screen.findByText("Dein Profil zeigt eine klare 7.");

    expect(api.workspaces.copilot.threads.list).not.toHaveBeenCalled();
    expect(api.workspaces.copilot.threads.messages.list).not.toHaveBeenCalled();
  });

  it("loads every message page so history is not truncated", async () => {
    const firstPage = Array.from({ length: 100 }, (_, index) => message({ id: `message-${index}` }));
    vi.mocked(api.me.copilot.threads.messages.list)
      .mockResolvedValueOnce(firstPage)
      .mockResolvedValueOnce([message({ id: "message-100", content: "Neueste Nachricht" })]);
    renderContent();

    expect(await screen.findByText("Neueste Nachricht")).toBeInTheDocument();
    expect(api.me.copilot.threads.messages.list).toHaveBeenNthCalledWith(2, "thread-personal", {
      limit: 100,
      offset: 100,
    });
  });

  it("rejects whitespace, recovers from a send failure and allows retry", async () => {
    vi.mocked(api.me.copilot.threads.messages.post)
      .mockRejectedValueOnce(new Error("Provider unavailable"))
      .mockResolvedValueOnce({
        user_message: message({ id: "user-3", role: "USER", author_user_id: "me", content: "Noch einmal", basis_type: null }),
        assistant_message: message({ id: "assistant-3", content: "Jetzt klappt es.", basis_type: "MIXED" }),
      });
    renderContent();
    await screen.findByText("Dein Profil zeigt eine klare 7.");

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

  it("discards a reply that arrives after the thread was archived and replaced", async () => {
    let resolvePost!: (value: Awaited<ReturnType<typeof api.me.copilot.threads.messages.post>>) => void;
    vi.mocked(api.me.copilot.threads.messages.post).mockReturnValue(new Promise((resolve) => { resolvePost = resolve; }));
    vi.mocked(api.me.copilot.threads.archive).mockResolvedValue({ ...thread(), archived_at: "2026-09-11T13:00:00Z" });
    vi.mocked(api.me.copilot.threads.create).mockResolvedValue(thread("thread-new"));
    vi.mocked(api.me.copilot.threads.messages.list).mockResolvedValueOnce([message()]).mockResolvedValueOnce([]);
    renderContent();
    await screen.findByText("Dein Profil zeigt eine klare 7.");

    fireEvent.change(screen.getByLabelText("Nachricht"), { target: { value: "Späte Antwort" } });
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));
    fireEvent.click(screen.getByRole("button", { name: "Gespräch archivieren" }));
    await screen.findByText("Noch keine Nachrichten in diesem Gespräch.");

    resolvePost({
      user_message: message({ id: "late-user", role: "USER", content: "Späte Antwort", basis_type: null }),
      assistant_message: message({ id: "late-assistant", content: "Nur im alten Verlauf", basis_type: "MIXED" }),
    });

    await waitFor(() => expect(api.me.copilot.threads.messages.post).toHaveBeenCalledTimes(1));
    expect(screen.queryByText("Nur im alten Verlauf")).not.toBeInTheDocument();
    expect(screen.getByText("Noch keine Nachrichten in diesem Gespräch.")).toBeInTheDocument();
  });

  it("reports a phase-gated failure through the callback instead of rendering an alert", async () => {
    const onPhaseDisabled = vi.fn();
    vi.mocked(api.me.copilot.threads.list).mockRejectedValue(
      new ApiError("phase disabled", "V2_PHASE_DISABLED", 403),
    );
    renderContent(onPhaseDisabled);

    await waitFor(() => expect(onPhaseDisabled).toHaveBeenCalledWith("V2_PHASE_DISABLED"));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
