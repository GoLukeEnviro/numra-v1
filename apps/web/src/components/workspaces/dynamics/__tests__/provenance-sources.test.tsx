import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProvenanceSources } from "@/components/workspaces/dynamics/provenance-sources";
import { LocaleProvider } from "@/i18n/context";

function renderSources(statement: Parameters<typeof ProvenanceSources>[0]["statement"]) {
  return render(
    <LocaleProvider>
      <ProvenanceSources statement={statement} />
    </LocaleProvider>,
  );
}

describe("ProvenanceSources", () => {
  it("is collapsed by default and toggles open", () => {
    renderSources({
      text: "x",
      canonical_refs: ["metric:a:life_path"],
      knowledge_refs: ["numbers#communication"],
      workspace_evidence_refs: [],
    });

    expect(screen.queryByText("metric:a:life_path")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Herkunft" }));
    expect(screen.getByText("metric:a:life_path")).toBeInTheDocument();
  });

  it("shows an empty ref group explicitly as 'keine' rather than hiding it", () => {
    renderSources({
      text: "x",
      canonical_refs: [],
      knowledge_refs: ["numbers#closeness"],
      workspace_evidence_refs: [],
    });

    fireEvent.click(screen.getByRole("button", { name: "Herkunft" }));
    expect(screen.getByText("Kanonische Werte")).toBeInTheDocument();
    expect(screen.getByText("Workspace-Belege")).toBeInTheDocument();
    expect(screen.getAllByText("keine")).toHaveLength(2);
  });
});
