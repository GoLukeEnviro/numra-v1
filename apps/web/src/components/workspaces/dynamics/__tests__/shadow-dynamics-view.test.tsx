import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ShadowDynamicsView } from "@/components/workspaces/dynamics/shadow-dynamics-view";
import { asShadowDynamicsResult } from "@/api/analysis-content";
import { shadowDynamicsResult } from "@/fixtures/analysis";
import { LocaleProvider } from "@/i18n/context";

const result = asShadowDynamicsResult(shadowDynamicsResult)!;

function renderView(over: Partial<typeof result> = {}) {
  return render(
    <LocaleProvider>
      <ShadowDynamicsView result={{ ...result, ...over }} />
    </LocaleProvider>,
  );
}

describe("ShadowDynamicsView", () => {
  it("renders both neutral person blocks, never a display name", () => {
    renderView();
    expect(screen.getByRole("heading", { name: "Person A" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Person B" })).toBeInTheDocument();
  });

  it("renders all seven result fields", () => {
    renderView();
    for (const heading of [
      "Person A",
      "Person B",
      "Interaktionsmuster",
      "Eskalationsschleife",
      "Ansatzpunkte zur Deeskalation",
      "Musterintensität",
      "Empfohlene Mikro-Schritte",
    ]) {
      expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
    }
  });

  it("shows pattern_intensity only as translated text — no number, bar, %, or progressbar", () => {
    const { container } = renderView({ pattern_intensity: "high" });
    expect(screen.getByText("hoch")).toBeInTheDocument();
    expect(within(container).queryByRole("progressbar")).not.toBeInTheDocument();
    expect(container.textContent).not.toMatch(/%/);
  });

  it("humanizes an unknown intensity value rather than dropping it", () => {
    renderView({ pattern_intensity: "very_high" });
    expect(screen.getByText("Very High")).toBeInTheDocument();
  });

  it("lists the micro-tasks as list items with the deterministic hint and no provenance", () => {
    renderView();
    const list = screen.getByRole("list");
    expect(within(list).getAllByRole("listitem")).toHaveLength(result.recommended_micro_tasks.length);
    expect(screen.getByText("Deterministisch aus dem Muster abgeleitet.")).toBeInTheDocument();
  });
});
