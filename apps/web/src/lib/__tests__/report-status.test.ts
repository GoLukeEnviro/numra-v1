import { describe, expect, it } from "vitest";
import {
  describeJobStatus,
  describeReportType,
  isJobTerminal,
  progressPercent,
  REPORT_TYPE_OPTIONS,
} from "@/lib/report-status";

describe("describeJobStatus", () => {
  it("marks only COMPLETE, FAILED and CANCELLED as terminal", () => {
    const terminal = [
      "QUEUED",
      "OUTLINE",
      "GENERATING",
      "VALIDATING",
      "ASSEMBLING",
      "COMPLETE",
      "FAILED",
      "CANCELLED",
    ].filter(isJobTerminal);
    expect(terminal).toEqual(["COMPLETE", "FAILED", "CANCELLED"]);
  });

  it("gives every ReportJobStatus a human label distinct from the raw enum", () => {
    expect(describeJobStatus("GENERATING").label).toBe("Writing");
    expect(describeJobStatus("ASSEMBLING").label).toBe("Assembling");
    expect(describeJobStatus("QUEUED").tone).toBe("pending");
    expect(describeJobStatus("COMPLETE").tone).toBe("done");
    expect(describeJobStatus("CANCELLED").tone).toBe("failed");
  });

  it("falls back to a non-terminal working state for an unknown status", () => {
    // The backend enum can grow ahead of this client; polling must not stop early
    // and the UI must not claim a state it does not know.
    const unknown = describeJobStatus("TRANSCRIBING");
    expect(unknown.label).toBe("TRANSCRIBING");
    expect(unknown.terminal).toBe(false);
    expect(isJobTerminal("TRANSCRIBING")).toBe(false);
  });
});

describe("progressPercent", () => {
  it("passes a valid progress value through unchanged", () => {
    expect(progressPercent(0)).toBe(0);
    expect(progressPercent(37)).toBe(37);
    expect(progressPercent(100)).toBe(100);
  });

  it("only clamps out-of-range values, never estimates a replacement", () => {
    expect(progressPercent(-5)).toBe(0);
    expect(progressPercent(140)).toBe(100);
    expect(progressPercent(Number.NaN)).toBe(0);
  });
});

describe("REPORT_TYPE_OPTIONS", () => {
  it("offers QUICK, FULL and ULTIMATE", () => {
    expect(REPORT_TYPE_OPTIONS.map((o) => o.value)).toEqual(["QUICK", "FULL", "ULTIMATE"]);
  });

  it("never offers CUSTOM, which POST /v1/reports cannot accept a word target for", () => {
    expect(REPORT_TYPE_OPTIONS.some((o) => String(o.value) === "CUSTOM")).toBe(false);
  });

  it("falls back to the raw value for a report type it has no label for", () => {
    expect(describeReportType("FULL")).toBe("Full");
    expect(describeReportType("CUSTOM")).toBe("CUSTOM");
  });
});
