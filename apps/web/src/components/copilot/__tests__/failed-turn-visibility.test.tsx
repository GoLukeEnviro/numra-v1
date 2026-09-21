import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PersonalCopilotContent } from "@/components/copilot/personal-copilot-content";
import { api, type ChatMessageOut, type ChatThreadOut } from "@/api/client";
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

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.me.copilot.threads.list).mockResolvedValue([thread()]);
});

describe("failed assistant turns are visible, never a blank bubble (#174)", () => {
  it("shows a localized hint and an accessible alert when the assistant turn FAILED", async () => {
    vi.mocked(api.me.copilot.threads.messages.list).mockResolvedValue([
      message({ id: "user-1", role: "USER", author_user_id: "me", content: "Wie stehe ich gerade?", basis_type: null }),
      message({
        id: "assistant-1",
        status: "FAILED",
        content: "",
        basis_type: null,
        error_code: "ANALYSIS_GENERATION_ERROR",
      }),
    ]);

    render(
      <LocaleProvider>
        <PersonalCopilotContent />
      </LocaleProvider>,
    );

    const hint = await screen.findByText(/konnte nicht gepr\u00fcft werden/i);
    expect(hint).toBeInTheDocument();
    // The failed turn must be announced, not just painted.
    expect(hint.closest("[role='alert']") ?? screen.getByRole("alert")).toBeTruthy();
  });

  it("keeps a COMPLETE assistant turn's text and shows no failure hint", async () => {
    vi.mocked(api.me.copilot.threads.messages.list).mockResolvedValue([message()]);

    render(
      <LocaleProvider>
        <PersonalCopilotContent />
      </LocaleProvider>,
    );

    expect(await screen.findByText("Dein Profil zeigt eine klare 7.")).toBeInTheDocument();
    expect(screen.queryByText(/konnte nicht gepr\u00fcft werden/i)).not.toBeInTheDocument();
  });

  it("renders a failure hint even when a FAILED turn carries partial content", async () => {
    vi.mocked(api.me.copilot.threads.messages.list).mockResolvedValue([
      message({
        id: "assistant-partial",
        status: "FAILED",
        content: "Teilweise Antwort",
        error_code: "ANALYSIS_GENERATION_ERROR",
      }),
    ]);

    render(
      <LocaleProvider>
        <PersonalCopilotContent />
      </LocaleProvider>,
    );

    expect(await screen.findByText("Teilweise Antwort")).toBeInTheDocument();
    expect(
      screen.getByText(/konnte nicht gepr\u00fcft werden/i),
    ).toBeInTheDocument();
  });
});
