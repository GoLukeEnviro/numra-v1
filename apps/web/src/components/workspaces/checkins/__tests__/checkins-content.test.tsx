import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CheckinsContent } from "@/components/workspaces/checkins/checkins-content";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { api, NetworkError, type CheckinOut, type CheckinTemplateOut, type WorkspaceOverviewOut } from "@/api/client";

vi.mock("next/navigation", () => ({
  usePathname: () => "/workspaces/ws-1/checkins",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));
vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));
vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return { ...actual, api: { ...actual.api, workspaces: {
    ...actual.api.workspaces,
    list: vi.fn(),
    checkins: { ...actual.api.workspaces.checkins, startRound: vi.fn(), submit: vi.fn(), get: vi.fn() },
    checkinDimensions: { ...actual.api.workspaces.checkinDimensions, create: vi.fn(), update: vi.fn() },
  }, connections: { ...actual.api.connections, list: vi.fn() } } };
});

const overview = (status: "ACTIVE" | "DISSOLVED" = "ACTIVE") => ({
  workspace: { id: "ws-1", connection_id: "conn-1", status, relationship_type: "PARTNER", created_at: "2026-01-01T00:00:00Z", dissolved_at: status === "DISSOLVED" ? "2026-09-01T00:00:00Z" : null },
  dual_profile: [
    { user_id: "me", display_name: "Lukas", self_person: null, core_numbers: null },
    { user_id: "them", display_name: "Ada", self_person: null, core_numbers: null },
  ],
}) as WorkspaceOverviewOut;

const template: CheckinTemplateOut = { id: "template-1", version: 1, active: true, dimensions: [
  { id: "dim-1", semantic_key: "closeness", label: "Nähe", description: "Wie verbunden fühlst du dich?", scale_min: 1, scale_max: 2, sort_order: 0, active: true, retired_at: null, dimension_class: null },
] };

const round = (overrides: Partial<CheckinOut> = {}): CheckinOut => ({
  id: "round-1", workspace_id: "ws-1", checkin_template_version: 1, status: "AWAITING_SUBMISSIONS", cycle_started_at: "2026-09-10T12:00:00Z", snapshot_origin: "ROUND_START", snapshot_recorded: true,
  dimensions: [{ dimension_id: "dim-1", semantic_key: "closeness", label: "Nähe", description: "Wie verbunden fühlst du dich?", scale_min: 1, scale_max: 2, sort_order: 0 }],
  my_responses: [], partner_submitted: false, analysis: null, ...overrides,
});

function renderContent(props: Partial<Parameters<typeof CheckinsContent>[0]> = {}) {
  return render(<LocaleProvider><CheckinsContent workspaceId="ws-1" overview={overview()} current={null} history={[]} template={template} onReload={vi.fn()} {...props} /></LocaleProvider>);
}

beforeEach(() => {
  sessionStorage.clear(); vi.clearAllMocks();
  vi.mocked(api.workspaces.list).mockResolvedValue([]);
  vi.mocked(api.connections.list).mockResolvedValue([]);
  vi.mocked(useAuth).mockReturnValue({ status: "authenticated", user: { id: "me" }, error: null } as ReturnType<typeof useAuth>);
});

describe("CheckinsContent", () => {
  it("starts a new round with a stable retry key", async () => {
    const onReload = vi.fn();
    vi.mocked(api.workspaces.checkins.startRound).mockRejectedValueOnce(new NetworkError(new TypeError("network"))).mockResolvedValueOnce(round());
    renderContent({ onReload });
    await screen.findByRole("heading", { name: "Ada", level: 1 });
    fireEvent.click(screen.getByRole("button", { name: /Runde starten/ }));
    expect(api.workspaces.checkins.startRound).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Jetzt verbindlich starten" }));
    await screen.findByRole("alert");
    const firstKey = vi.mocked(api.workspaces.checkins.startRound).mock.calls[0]?.[1];
    fireEvent.click(screen.getByRole("button", { name: "Jetzt verbindlich starten" }));
    await waitFor(() => expect(onReload).toHaveBeenCalledOnce());
    expect(vi.mocked(api.workspaces.checkins.startRound).mock.calls[1]?.[1]).toBe(firstKey);
    expect(onReload).toHaveBeenCalledOnce();
  });

  it("requires every snapshot answer and submits the snapshot dimension id", async () => {
    const onReload = vi.fn();
    vi.mocked(api.workspaces.checkins.submit).mockResolvedValue(round({ my_responses: [{ dimension_id: "dim-1", semantic_key: "closeness", value: 2, submitted_at: "2026-09-10T12:01:00Z" }] }));
    renderContent({ current: round(), onReload });
    await screen.findByRole("heading", { name: "Ada", level: 1 });
    expect(screen.getByRole("button", { name: "Antworten verbindlich abgeben" })).toBeDisabled();
    fireEvent.click(screen.getByRole("radio", { name: "2" }));
    fireEvent.click(screen.getByRole("button", { name: "Antworten verbindlich abgeben" }));
    await waitFor(() => expect(api.workspaces.checkins.submit).toHaveBeenCalledWith("ws-1", { round_id: "round-1", responses: [{ dimension_id: "dim-1", value: 2 }] }, expect.any(String)));
  });

  it("keeps an uncertain submit retryable without storing raw response values", async () => {
    vi.mocked(api.workspaces.checkins.submit).mockRejectedValue(new NetworkError(new TypeError("offline")));
    const view = renderContent({ current: round() });
    await screen.findByRole("heading", { name: "Ada", level: 1 });
    fireEvent.click(screen.getByRole("radio", { name: "2" }));
    fireEvent.click(screen.getByRole("button", { name: "Antworten verbindlich abgeben" }));
    await screen.findByText(/Netzwerkunterbrechung unklar/);
    const stored = sessionStorage.getItem("avenyth:checkin-attempt:v1:me:ws-1:submit");
    expect(stored).toContain("round-1");
    expect(stored).not.toContain('"value"');
    expect(screen.getByRole("radio", { name: "2" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Denselben Versuch wiederholen" })).toBeEnabled();
    view.unmount();
    renderContent({ current: round() });
    expect(screen.getByRole("radio", { name: "2" })).toBeChecked();
    expect(screen.getByRole("button", { name: "Denselben Versuch wiederholen" })).toBeEnabled();
  });

  it("renders a null historical delta as unavailable and explains the privacy boundary", async () => {
    renderContent({ current: round({ status: "ANALYZED", my_responses: [{ dimension_id: "dim-1", semantic_key: "closeness", value: 2, submitted_at: "2026-09-10T12:01:00Z" }], partner_submitted: true, analysis: { computed_at: "2026-09-10T12:02:00Z", result: { closeness: { absolute_gap: 1, direction: "STABLE", rolling_trend: 1, sample_size: 1, historical_delta: null, sufficient_evidence: false } } } }) });
    await screen.findByRole("heading", { name: "Ada", level: 1 });
    expect(screen.getByText("Noch nicht verfügbar")).toBeInTheDocument();
    expect(screen.getByText(/Partner-Rohantworten werden nicht direkt angezeigt/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Deine Antworten" })).toBeInTheDocument();
  });

  it("shows an empty historical view without mutation controls after dissolution", async () => {
    renderContent({ overview: overview("DISSOLVED"), current: null, template: null });
    await screen.findByRole("heading", { name: "Ada", level: 1 });
    expect(screen.getByRole("heading", { name: "Historische Ansicht" })).toBeInTheDocument();
    expect(screen.getByText(/keine historische Check-in-Runde/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Runde starten/ })).not.toBeInTheDocument();
  });

  it("locks every configuration action while a round is open", async () => {
    renderContent({ current: round() });
    await screen.findByRole("heading", { name: "Ada", level: 1 });
    expect(screen.getByRole("button", { name: "Bearbeiten" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Deaktivieren" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Frage hinzufügen" })).not.toBeInTheDocument();
  });

  it("loads a selected historical round and labels migrated provenance honestly", async () => {
    const historic = round({ id: "historic-1", status: "ANALYZED", snapshot_origin: "MIGRATION_CURRENT", analysis: { computed_at: "2026-09-10T12:02:00Z", result: { closeness: { absolute_gap: 1, direction: "NO_PRIOR_DATA", rolling_trend: 1, sample_size: 1, historical_delta: null, sufficient_evidence: false } } } });
    vi.mocked(api.workspaces.checkins.get).mockResolvedValue(historic);
    renderContent({ history: [{ id: "historic-1", status: "ANALYZED", cycle_started_at: historic.cycle_started_at, checkin_template_version: 1 }] });
    await screen.findByRole("heading", { name: "Ada", level: 1 });
    fireEvent.click(screen.getByRole("button", { name: /Fragenversion 1/ }));
    expect(await screen.findByText(/erst bei der Migration festgehalten/)).toBeInTheDocument();
    expect(screen.getByText("Noch keine Vordaten")).toBeInTheDocument();
  });
});
