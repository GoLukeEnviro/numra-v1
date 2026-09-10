import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RelationshipAnalysisView } from "@/components/workspaces/dynamics/relationship-analysis-view";
import { asRelationshipAnalysisResult } from "@/api/analysis-content";
import { relationshipAnalysisResult } from "@/fixtures/analysis";
import { LocaleProvider } from "@/i18n/context";

const result = asRelationshipAnalysisResult(relationshipAnalysisResult)!;

function renderView() {
  return render(
    <LocaleProvider>
      <RelationshipAnalysisView result={result} />
    </LocaleProvider>,
  );
}

describe("RelationshipAnalysisView", () => {
  it("labels each dimension via the curated i18n map", () => {
    renderView();
    expect(screen.getByRole("heading", { name: "Kommunikation" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Nähe" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Konfliktdynamik" })).toBeInTheDocument();
  });

  it("renders provenance for every statement, including empty workspace-evidence groups", () => {
    renderView();
    const toggles = screen.getAllByRole("button", { name: "Herkunft" });
    expect(toggles).toHaveLength(result.dimensions.length);
    toggles.forEach((toggle) => fireEvent.click(toggle));
    // the communication statement has an empty workspace_evidence_refs group
    expect(screen.getAllByText("keine").length).toBeGreaterThan(0);
    expect(screen.getAllByText("metric:a:life_path").length).toBeGreaterThan(0);
  });

  it("shows the versions footer verbatim and no compatibility score", () => {
    const { container } = renderView();
    expect(screen.getByText("de-rel-v1")).toBeInTheDocument();
    expect(screen.getByText("mock / mock-relationship-1")).toBeInTheDocument();
    expect(within(container).queryByText(/%/)).not.toBeInTheDocument();
    expect(within(container).queryByRole("progressbar")).not.toBeInTheDocument();
  });
});
