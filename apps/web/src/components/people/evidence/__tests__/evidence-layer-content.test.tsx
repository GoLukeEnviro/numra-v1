import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, type EvidenceResultOut, type LifeTrackingEntryOut } from "@/api/client";
import { EvidenceLayerContent } from "@/components/people/evidence/evidence-layer-content";
import { LocaleProvider } from "@/i18n/context";

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    api: {
      people: {
        lifeTracking: { list: vi.fn(), create: vi.fn(), remove: vi.fn() },
        customMetrics: { list: vi.fn(), create: vi.fn(), patch: vi.fn() },
      },
      evidence: { result: vi.fn(), analyses: { list: vi.fn(), create: vi.fn(), remove: vi.fn() } },
    },
  };
});

const entry: LifeTrackingEntryOut = {
  id: "entry-1",
  person_id: "person-1",
  entry_date: "2026-09-11",
  calculation_id: null,
  mood: 7,
  energy: 6,
  sleep: 8,
  stress: 3,
  focus: 7,
  note: "Ruhiger Arbeitstag",
  custom_metrics: {},
  created_at: "2026-09-11T18:00:00Z",
  updated_at: "2026-09-11T18:00:00Z",
};

const reliable: EvidenceResultOut = {
  sample_size: 18,
  observation_window_days: 42,
  confidence_category: "MEDIUM",
  effect_size: 0.44,
  baseline_mean: 5.4,
  bucket_mean: 6.8,
  statement_text: "An den bislang beobachteten Personal-Day-5-Tagen lag deine gemessene Energie im Mittel höher als deine persönliche Baseline.",
  evidence_policy_version: 1,
};

function renderContent() {
  return render(<LocaleProvider><EvidenceLayerContent personId="person-1" personName="Lukas" /></LocaleProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.people.lifeTracking.list).mockResolvedValue([entry]);
  vi.mocked(api.evidence.analyses.list).mockResolvedValue([]);
  vi.mocked(api.people.customMetrics.list).mockResolvedValue([]);
});

describe("EvidenceLayerContent", () => {
  it("renders the observation journal with privacy-safe metric history", async () => {
    renderContent();
    expect(await screen.findByRole("heading", { name: "Beobachtungsjournal" })).toBeInTheDocument();
    expect(screen.getByText("Ruhiger Arbeitstag")).toBeInTheDocument();
    expect(screen.getByText("Stimmung 7/10")).toBeInTheDocument();
    expect(api.people.lifeTracking.list).toHaveBeenCalledWith("person-1", { limit: 200, offset: 0 });
  });

  it("creates, records, and retires a custom metric without changing its immutable key", async () => {
    const definition = {
      id: "metric-1", person_id: "person-1", metric_key: "creativity", label: "Kreativität",
      scale_min: 1, scale_max: 10, active: true, created_at: "2026-09-12T08:00:00Z", retired_at: null,
    };
    vi.mocked(api.people.customMetrics.create).mockResolvedValue(definition);
    vi.mocked(api.people.customMetrics.patch).mockResolvedValue({ ...definition, active: false, retired_at: "2026-09-12T09:00:00Z" });
    vi.mocked(api.people.lifeTracking.create).mockResolvedValue({ ...entry, id: "entry-custom", custom_metrics: { creativity: 9 } });
    renderContent();
    await screen.findByText("Ruhiger Arbeitstag");

    fireEvent.change(screen.getByLabelText("Technischer Schlüssel"), { target: { value: "creativity" } });
    fireEvent.change(screen.getByLabelText("Anzeigename"), { target: { value: "Kreativität" } });
    fireEvent.click(screen.getByRole("button", { name: "Messwert anlegen" }));
    expect(await screen.findByLabelText("Kreativität")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Kreativität"), { target: { value: "9" } });
    fireEvent.click(screen.getByRole("button", { name: "Tag speichern" }));
    await waitFor(() => expect(api.people.lifeTracking.create).toHaveBeenCalledWith("person-1", expect.objectContaining({ custom_metrics: { creativity: 9 } })));

    fireEvent.click(screen.getByRole("button", { name: "Kreativität stilllegen" }));
    await waitFor(() => expect(api.people.customMetrics.patch).toHaveBeenCalledWith("metric-1", { active: false }));
    expect(screen.queryByLabelText("Kreativität")).not.toBeInTheDocument();
  });

  it("uses server-defined scales and retains retired metric history", async () => {
    vi.mocked(api.people.customMetrics.list).mockResolvedValue([
      { id: "metric-active", person_id: "person-1", metric_key: "calm", label: "Ruhe", scale_min: 0, scale_max: 5, active: true, created_at: "2026-09-10T08:00:00Z", retired_at: null },
      { id: "metric-retired", person_id: "person-1", metric_key: "clarity", label: "Klarheit", scale_min: 2, scale_max: 7, active: false, created_at: "2026-09-01T08:00:00Z", retired_at: "2026-09-10T08:00:00Z" },
    ]);
    vi.mocked(api.people.lifeTracking.list).mockResolvedValue([{ ...entry, custom_metrics: { calm: 0, clarity: 6 } }]);
    renderContent();

    const select = await screen.findByLabelText<HTMLSelectElement>("Ruhe");
    expect([...select.options].map((option) => option.value)).toEqual(["", "0", "1", "2", "3", "4", "5"]);
    expect(screen.getByText("Ruhe 0/5")).toBeInTheDocument();
    expect(screen.getByText("Klarheit 6/7")).toBeInTheDocument();
    expect(screen.queryByLabelText("Klarheit")).not.toBeInTheDocument();
  });

  it("creates a daily entry with numeric metrics and refreshes the journal", async () => {
    vi.mocked(api.people.lifeTracking.create).mockResolvedValue({ ...entry, id: "entry-2", entry_date: "2026-09-12", mood: 8, energy: 7, note: "Klarer Fokus" });
    renderContent();
    await screen.findByText("Ruhiger Arbeitstag");

    fireEvent.change(screen.getByLabelText("Datum"), { target: { value: "2026-09-12" } });
    fireEvent.change(screen.getByLabelText("Stimmung"), { target: { value: "8" } });
    fireEvent.change(screen.getByLabelText("Energie"), { target: { value: "7" } });
    fireEvent.change(screen.getByLabelText("Notiz (optional)"), { target: { value: "Klarer Fokus" } });
    fireEvent.click(screen.getByRole("button", { name: "Tag speichern" }));

    await waitFor(() => expect(api.people.lifeTracking.create).toHaveBeenCalledWith("person-1", expect.objectContaining({
      entry_date: "2026-09-12", mood: 8, energy: 7, note: "Klarer Fokus",
    })));
    expect(await screen.findByText("Klarer Fokus")).toBeInTheDocument();
  });

  it("shows a reliable result with every mandatory qualifier and can save the server result", async () => {
    vi.mocked(api.evidence.result).mockResolvedValue(reliable);
    vi.mocked(api.evidence.analyses.create).mockResolvedValue({
      id: "analysis-1", person_id: "person-1", metric_key: "energy", correlation_target: "PERSONAL_DAY",
      correlation_target_value: 5, evidence_policy_version: 1, result: reliable, created_at: "2026-09-12T08:00:00Z",
    });
    renderContent();
    await screen.findByText("Ruhiger Arbeitstag");

    fireEvent.click(screen.getByRole("button", { name: "Muster prüfen" }));

    expect(await screen.findByText(reliable.statement_text!)).toBeInTheDocument();
    expect(screen.getByText("18 Beobachtungen")).toBeInTheDocument();
    expect(screen.getByText("42 Tage Zeitraum")).toBeInTheDocument();
    expect(screen.getByText("Mittlere Sicherheit")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Analyse speichern" }));
    await waitFor(() => expect(api.evidence.analyses.create).toHaveBeenCalledWith("person-1", {
      metric_key: "mood", correlation_target: "PERSONAL_DAY", correlation_target_value: 1,
    }));
  });

  it("renders NO_RELIABLE_PATTERN as a valid building state, not an error", async () => {
    vi.mocked(api.evidence.result).mockResolvedValue({
      ...reliable, sample_size: 3, observation_window_days: 5, confidence_category: "NO_RELIABLE_PATTERN",
      effect_size: null, baseline_mean: null, bucket_mean: null, statement_text: null,
    });
    renderContent();
    await screen.findByText("Ruhiger Arbeitstag");
    fireEvent.click(screen.getByRole("button", { name: "Muster prüfen" }));

    expect(await screen.findByText("Noch kein belastbares Muster")).toBeInTheDocument();
    expect(screen.getByText("3 Beobachtungen")).toBeInTheDocument();
    expect(screen.getByText("5 Tage Zeitraum")).toBeInTheDocument();
    expect(screen.getByText("Noch nicht belastbar")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("keeps all mandatory qualifiers beside a saved correlation statement", async () => {
    vi.mocked(api.evidence.analyses.list).mockResolvedValue([{
      id: "saved-1", person_id: "person-1", metric_key: "energy", correlation_target: "PERSONAL_DAY",
      correlation_target_value: 5, evidence_policy_version: 1, result: reliable, created_at: "2026-09-12T08:00:00Z",
    }]);
    renderContent();

    expect(await screen.findByText(reliable.statement_text!)).toBeInTheDocument();
    expect(screen.getByText("18 Beobachtungen")).toBeInTheDocument();
    expect(screen.getByText("42 Tage Zeitraum")).toBeInTheDocument();
    expect(screen.getByText("Mittlere Sicherheit")).toBeInTheDocument();
    expect(screen.getByText(/belegt keine Ursache/)).toBeInTheDocument();
  });

  it("saves the exact query that produced the displayed result", async () => {
    vi.mocked(api.evidence.result).mockResolvedValue(reliable);
    vi.mocked(api.evidence.analyses.create).mockResolvedValue({
      id: "saved-2", person_id: "person-1", metric_key: "mood", correlation_target: "PERSONAL_DAY",
      correlation_target_value: 1, evidence_policy_version: 1, result: reliable, created_at: "2026-09-12T08:00:00Z",
    });
    renderContent();
    await screen.findByText("Ruhiger Arbeitstag");
    fireEvent.click(screen.getByRole("button", { name: "Muster prüfen" }));
    await screen.findByText(reliable.statement_text!);
    fireEvent.change(screen.getByLabelText("Messwert"), { target: { value: "energy" } });
    fireEvent.change(screen.getByLabelText("Zahl"), { target: { value: "5" } });
    fireEvent.click(screen.getByRole("button", { name: "Analyse speichern" }));

    await waitFor(() => expect(api.evidence.analyses.create).toHaveBeenCalledWith("person-1", {
      metric_key: "mood", correlation_target: "PERSONAL_DAY", correlation_target_value: 1,
    }));
  });

  it("invalidates a displayed result after its tracking dataset changes", async () => {
    vi.mocked(api.evidence.result).mockResolvedValue(reliable);
    vi.mocked(api.people.lifeTracking.create).mockResolvedValue({ ...entry, id: "entry-2", entry_date: "2026-09-12", mood: 8 });
    renderContent();
    await screen.findByText("Ruhiger Arbeitstag");
    fireEvent.click(screen.getByRole("button", { name: "Muster prüfen" }));
    await screen.findByText(reliable.statement_text!);

    fireEvent.change(screen.getByLabelText("Stimmung"), { target: { value: "8" } });
    fireEvent.click(screen.getByRole("button", { name: "Tag speichern" }));

    await waitFor(() => expect(api.people.lifeTracking.create).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.queryByText(reliable.statement_text!)).not.toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Analyse speichern" })).not.toBeInTheDocument();
  });

  it("prevents journal mutations while an evidence check is in flight", async () => {
    let resolveResult!: (value: EvidenceResultOut) => void;
    vi.mocked(api.evidence.result).mockReturnValue(new Promise((resolve) => { resolveResult = resolve; }));
    renderContent();
    await screen.findByText("Ruhiger Arbeitstag");

    fireEvent.click(screen.getByRole("button", { name: "Muster prüfen" }));
    expect(screen.getByRole("button", { name: "Tag speichern" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Beobachtung löschen" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Beobachtung löschen" }));
    expect(api.people.lifeTracking.remove).not.toHaveBeenCalled();

    resolveResult(reliable);
    expect(await screen.findByText(reliable.statement_text!)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Beobachtung löschen" })).toBeEnabled();
  });

  it("reports delete failures without removing the observation", async () => {
    vi.mocked(api.people.lifeTracking.remove).mockRejectedValue(new Error("Löschen fehlgeschlagen"));
    renderContent();
    await screen.findByText("Ruhiger Arbeitstag");
    fireEvent.click(screen.getByRole("button", { name: "Beobachtung löschen" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Löschen fehlgeschlagen");
    expect(screen.getByText("Ruhiger Arbeitstag")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Beobachtung löschen" })).toBeEnabled();
  });

  it("switches to the calm disabled state when the phase closes during an action", async () => {
    vi.mocked(api.evidence.result).mockRejectedValue(new ApiError("disabled", "V2_PHASE_DISABLED", 409));
    renderContent();
    await screen.findByText("Ruhiger Arbeitstag");
    fireEvent.click(screen.getByRole("button", { name: "Muster prüfen" }));

    expect(await screen.findByText("Evidence Layer noch nicht verfügbar")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renders a phase-disabled response as a calm availability state", async () => {
    vi.mocked(api.people.lifeTracking.list).mockRejectedValue(new ApiError("disabled", "V2_PHASE_DISABLED", 409));
    renderContent();

    expect(await screen.findByText("Evidence Layer noch nicht verfügbar")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
