import { describe, expect, it } from "vitest";
import {
  describeAnalysisJobStatus,
  humanizeSnakeCase,
  isAnalysisJobTerminal,
} from "@/lib/analysis-status";

describe("describeAnalysisJobStatus", () => {
  it("marks only COMPLETE and FAILED as terminal", () => {
    const terminal = ["QUEUED", "GENERATING", "VALIDATING", "COMPLETE", "FAILED"].filter(
      isAnalysisJobTerminal,
    );
    expect(terminal).toEqual(["COMPLETE", "FAILED"]);
  });

  it("gives every status a human label distinct from the raw enum", () => {
    expect(describeAnalysisJobStatus("GENERATING").label).toBe("Generating");
    expect(describeAnalysisJobStatus("QUEUED").tone).toBe("pending");
    expect(describeAnalysisJobStatus("COMPLETE").tone).toBe("done");
    expect(describeAnalysisJobStatus("FAILED").tone).toBe("failed");
  });

  it("falls back to a non-terminal working state for an unknown status", () => {
    const unknown = describeAnalysisJobStatus("SYNTHESIZING");
    expect(unknown.label).toBe("SYNTHESIZING");
    expect(unknown.terminal).toBe(false);
    expect(isAnalysisJobTerminal("SYNTHESIZING")).toBe(false);
  });
});

describe("humanizeSnakeCase", () => {
  it("turns a snake_case id into Title Case", () => {
    expect(humanizeSnakeCase("conflict_dynamics")).toBe("Conflict Dynamics");
    expect(humanizeSnakeCase("power_dynamics")).toBe("Power Dynamics");
    expect(humanizeSnakeCase("moderate")).toBe("Moderate");
  });

  it("collapses repeated and surrounding separators", () => {
    expect(humanizeSnakeCase("  shared__history ")).toBe("Shared History");
  });
});
