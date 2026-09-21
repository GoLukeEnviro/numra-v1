import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { WorkspaceCopilotContent } from "@/components/workspaces/copilot/workspace-copilot-content";
import {
  api,
  type ChatMessageOut,
  type ChatThreadOut,
  type WorkspaceOverviewOut,
} from "@/api/client";
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

function thread(scope: "RELATIONSHIP_SHARED" | "RELATIONSHIP_PRIVATE" = "RELATIONSHIP_SHARED"): ChatThreadOut {
  return {
    id: "thread-shared",
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

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(useAuth).mockReturnValue({
    status: "authenticated",
    user: { id: "me" },
    error: null,
  } as ReturnType<typeof useAuth>);
  vi.mocked(api.workspaces.list).mockResolvedValue([]);
  vi.mocked(api.connections.list).mockResolvedValue([]);
  vi.mocked(api.workspaces.copilot.threads.list).mockResolvedValue([thread()]);
  vi.mocked(api.workspaces.copilot.threads.get).mockResolvedValue(thread());
  vi.mocked(api.workspaces.copilot.threads.messages.list).mockResolvedValue([message()]);
});

describe("workspace copilot: failed turns are visible (#174)", () => {
  it("shows the localized failure hint instead of an empty answer bubble", async () => {
    vi.mocked(api.workspaces.copilot.threads.messages.list).mockResolvedValue([
      message({ id: "user-1", role: "USER", author_user_id: "me", content: "Wie läuft es bei uns?", basis_type: null }),
      message({ id: "assistant-1", status: "FAILED", content: "", basis_type: null, error_code: "ANALYSIS_GENERATION_ERROR" }),
    ]);

    render(
      <LocaleProvider>
        <WorkspaceCopilotContent workspaceId="ws-1" overview={overview} />
      </LocaleProvider>,
    );

    const hint = await screen.findByText(/konnte nicht gepr\u00fcft werden/i);
    expect(hint).toBeInTheDocument();
    expect(hint.closest("[role='alert']")).not.toBeNull();
  });
});
