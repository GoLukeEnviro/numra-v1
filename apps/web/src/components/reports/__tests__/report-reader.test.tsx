import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ReportReader } from "@/components/reports/report-reader";
import type { ReportOut } from "@/api/client";
import type { StructuredReport } from "@/api/report-content";

const baseReport: ReportOut = {
  id: "report-1",
  job_id: "job-1",
  calculation_id: "calc-1",
  calculation_version: "1.0.0",
  knowledge_version: "1.1.0",
  prompt_version: "numra-report-v1",
  report_type: "QUICK",
  status: "COMPLETE",
  content: null,
  created_at: "2026-08-22T00:00:00Z",
  generated_at: "2026-08-22T00:05:00Z",
};

function contentWith(sections: StructuredReport["sections"]): StructuredReport {
  return {
    report_type: "QUICK",
    language: "de",
    calculation_version: "1.0.0",
    knowledge_version: "1.1.0",
    prompt_version: "numra-report-v1",
    model_provider: "mock",
    model_name: "mock-v1",
    total_word_count: sections.reduce((sum, s) => sum + s.word_count, 0),
    sections,
  };
}

describe("ReportReader — V1.5 Epic M provenance", () => {
  it("shows a Sources disclosure with metric and knowledge refs when present", () => {
    const content = contentWith([
      {
        section_id: "life_path",
        title: "Life Path",
        order_index: 0,
        text: "Body text.",
        word_count: 2,
        summary: "",
        metric_refs: ["life_path"],
        knowledge_refs: ["life_path"],
      },
    ]);
    render(<ReportReader report={baseReport} content={content} />);

    const toggle = screen.getByRole("button", { name: "Sources" });
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Profile metrics")).toBeInTheDocument();
    expect(screen.getByText("Knowledge entries")).toBeInTheDocument();
    expect(screen.getAllByText("life_path").length).toBeGreaterThan(0);
  });

  it("renders no Sources disclosure for a section without refs (backward compat)", () => {
    const content = contentWith([
      {
        section_id: "life_path",
        title: "Life Path",
        order_index: 0,
        text: "Body text.",
        word_count: 2,
        summary: "",
      },
    ]);
    render(<ReportReader report={baseReport} content={content} />);
    expect(screen.queryByRole("button", { name: "Sources" })).not.toBeInTheDocument();
  });
});
