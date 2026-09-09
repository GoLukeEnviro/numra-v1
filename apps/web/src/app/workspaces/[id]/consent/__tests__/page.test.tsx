import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import WorkspaceConsentPage from "@/app/workspaces/[id]/consent/page";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/api/client";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "workspace-1" }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/workspaces/workspace-1/consent",
}));

vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    api: {
      workspaces: {
        get: vi.fn(),
        consent: { list: vi.fn(), grant: vi.fn(), revoke: vi.fn() },
      },
    },
  };
});

function renderPage() {
  return render(
    <LocaleProvider>
      <WorkspaceConsentPage />
    </LocaleProvider>,
  );
}

const OVERVIEW = {
  workspace: {
    id: "workspace-1",
    connection_id: "conn-1",
    status: "ACTIVE" as const,
    relationship_type: null,
    created_at: "2026-09-01T00:00:00Z",
    dissolved_at: null,
  },
  dual_profile: [
    { user_id: "user-1", display_name: "Me", self_person: null, core_numbers: null },
    { user_id: "user-2", display_name: "Ada Lovelace", self_person: null, core_numbers: null },
  ],
};

function grant(scope: string, grantorId: string, granteeId: string) {
  return {
    id: `grant-${scope}-${grantorId}`,
    workspace_id: "workspace-1",
    grantor_user_id: grantorId,
    grantee_user_id: granteeId,
    scope,
    granted_at: "2026-09-01T00:00:00Z",
    revoked_at: null,
    version: 1,
  };
}

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({
    status: "authenticated",
    user: { id: "user-1", email: "me@example.com", role: "USER", is_active: true } as never,
    error: null,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
  });
  vi.mocked(api.workspaces.get).mockReset().mockResolvedValue(OVERVIEW as never);
  vi.mocked(api.workspaces.consent.list).mockReset();
  vi.mocked(api.workspaces.consent.grant).mockReset();
  vi.mocked(api.workspaces.consent.revoke).mockReset();
});

describe("WorkspaceConsentPage", () => {
  it("separates outgoing and incoming into two panels -- incoming has no interactive elements", async () => {
    vi.mocked(api.workspaces.consent.list).mockResolvedValue({
      granted_by_me: [grant("CORE_NUMEROLOGY", "user-1", "user-2")],
      granted_to_me: [grant("CORE_NUMEROLOGY", "user-2", "user-1")],
    } as never);
    renderPage();

    const sharedByMe = (await screen.findByText("Von mir geteilt")).closest(
      "[class*='rounded']",
    )! as HTMLElement;
    const sharedWithMe = screen.getByText("Mit mir geteilt").closest(
      "[class*='rounded']",
    )! as HTMLElement;

    expect(within(sharedByMe).getAllByRole("switch").length).toBeGreaterThan(0);
    expect(within(sharedWithMe).queryAllByRole("switch")).toHaveLength(0);
    expect(within(sharedWithMe).queryAllByRole("button")).toHaveLength(0);
  });

  it("does not flip the toggle before the grant response resolves", async () => {
    vi.mocked(api.workspaces.consent.list).mockResolvedValue({
      granted_by_me: [],
      granted_to_me: [],
    } as never);
    let resolveGrant: (value: unknown) => void = () => {};
    vi.mocked(api.workspaces.consent.grant).mockReturnValue(
      new Promise((resolve) => {
        resolveGrant = resolve;
      }) as never,
    );
    renderPage();

    const toggle = (await screen.findAllByRole("switch"))[3]!; // first PRIVATE_JOURNAL toggle
    expect(toggle).toHaveAttribute("aria-checked", "false");

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(toggle).toBeDisabled();

    await act(async () => {
      resolveGrant(grant("PRIVATE_JOURNAL", "user-1", "user-2"));
    });
    expect(toggle).toHaveAttribute("aria-checked", "true");
  });

  it("does not call any API when clicking an incoming (read-only) badge row", async () => {
    vi.mocked(api.workspaces.consent.list).mockResolvedValue({
      granted_by_me: [],
      granted_to_me: [grant("CORE_NUMEROLOGY", "user-2", "user-1")],
    } as never);
    renderPage();

    await screen.findByText("Freigegeben");
    fireEvent.click(screen.getByText("Freigegeben"));

    expect(api.workspaces.consent.grant).not.toHaveBeenCalled();
    expect(api.workspaces.consent.revoke).not.toHaveBeenCalled();
  });

  it("immediately reflects a revoke after the response resolves", async () => {
    vi.mocked(api.workspaces.consent.list).mockResolvedValue({
      granted_by_me: [grant("CORE_NUMEROLOGY", "user-1", "user-2")],
      granted_to_me: [],
    } as never);
    vi.mocked(api.workspaces.consent.revoke).mockResolvedValue({
      ...grant("CORE_NUMEROLOGY", "user-1", "user-2"),
      revoked_at: "2026-09-06T00:00:00Z",
    } as never);
    renderPage();

    const toggle = (await screen.findAllByRole("switch"))[0]!;
    expect(toggle).toHaveAttribute("aria-checked", "true");

    await act(async () => {
      fireEvent.click(toggle);
    });

    expect(api.workspaces.consent.revoke).toHaveBeenCalledWith("workspace-1", {
      scope: "CORE_NUMEROLOGY",
    });
    expect(toggle).toHaveAttribute("aria-checked", "false");
  });
});
