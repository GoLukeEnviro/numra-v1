import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConsentSummaryCard } from "@/components/workspaces/consent-summary-card";
import { LocaleProvider } from "@/i18n/context";
import { api, type WorkspaceConsentOut } from "@/api/client";

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return { ...actual, api: { workspaces: { consent: { list: vi.fn() } } } };
});

function renderCard() {
  return render(
    <LocaleProvider>
      <ConsentSummaryCard workspaceId="ws-1" counterpartName="Ada Lovelace" />
    </LocaleProvider>,
  );
}

beforeEach(() => {
  vi.mocked(api.workspaces.consent.list).mockReset();
});

describe("ConsentSummaryCard", () => {
  it("renders the aggregated counts for both directions with a link to the consent page", async () => {
    const data: WorkspaceConsentOut = {
      granted_by_me: [
        { id: "g1", workspace_id: "ws-1", grantor_user_id: "me", grantee_user_id: "them", scope: "CORE_NUMEROLOGY", granted_at: "2026-01-01T00:00:00Z", revoked_at: null, version: 1 },
      ],
      granted_to_me: [
        { id: "g2", workspace_id: "ws-1", grantor_user_id: "them", grantee_user_id: "me", scope: "CURRENT_TIMING", granted_at: "2026-01-01T00:00:00Z", revoked_at: null, version: 1 },
        { id: "g3", workspace_id: "ws-1", grantor_user_id: "them", grantee_user_id: "me", scope: "RELATIONSHIP_INSIGHTS", granted_at: "2026-01-01T00:00:00Z", revoked_at: null, version: 1 },
      ],
    };
    vi.mocked(api.workspaces.consent.list).mockResolvedValue(data);
    renderCard();

    expect(await screen.findByText(/von 8 Bereichen$/)).toBeInTheDocument();
    expect(screen.getByText(/von 8 Bereichen mit dir/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Freigaben verwalten" })).toHaveAttribute(
      "href",
      "/workspaces/ws-1/consent",
    );
  });
});
