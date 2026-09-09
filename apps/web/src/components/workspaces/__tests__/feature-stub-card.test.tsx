import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FeatureStubCard } from "@/components/workspaces/feature-stub-card";

describe("FeatureStubCard", () => {
  it("renders the eyebrow, title and description passed in", () => {
    render(<FeatureStubCard eyebrow="Dynamics" title="Dynamics" description="Coming soon." />);
    expect(screen.getAllByText("Dynamics")).toHaveLength(2);
    expect(screen.getByText("Coming soon.")).toBeInTheDocument();
  });
});
