import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ReportReader } from "@/components/reports/report-reader";
import { LocaleProvider } from "@/i18n/context";
import type { ReportOut } from "@/api/client";
import type { StructuredReport } from "@/api/report-content";

function renderReader(props: Parameters<typeof ReportReader>[0]) {
  return render(
    <LocaleProvider>
      <ReportReader {...props} />
    </LocaleProvider>,
  );
}

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
  content_flag: "none",
  flagged_section_ids: [],
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
    renderReader({ report: baseReport, content });

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
    renderReader({ report: baseReport, content });
    expect(screen.queryByRole("button", { name: "Sources" })).not.toBeInTheDocument();
  });
});

describe("ReportReader - D6 content flag", () => {
  const sections = [
    {
      section_id: "life_path",
      title: "Life Path",
      order_index: 0,
      text: "Body text.",
      word_count: 2,
      summary: "{{metric:a:life_path}}",
    },
    {
      section_id: "expression",
      title: "Expression",
      order_index: 1,
      text: "Other text.",
      word_count: 2,
      summary: "",
    },
  ];

  it("shows no notice and no section badge for an unflagged report", () => {
    renderReader({ report: baseReport, content: contentWith(sections) });
    expect(screen.queryByTestId("content-flag-notice")).not.toBeInTheDocument();
    expect(screen.queryByText("Enthält Platzhalter")).not.toBeInTheDocument();
  });

  it("flags the report and only the affected section, text stays as stored", () => {
    renderReader({
      report: {
        ...baseReport,
        content_flag: "unresolved_template_tokens",
        flagged_section_ids: ["life_path"],
      },
      content: contentWith(sections),
    });
    expect(screen.getByText("Dieser Inhalt enthält technische Platzhalter")).toBeInTheDocument();
    expect(screen.getAllByText("Enthält Platzhalter")).toHaveLength(1);
    // not hidden, not rewritten: the stored summary is still rendered verbatim
    expect(screen.getByText("{{metric:a:life_path}}")).toBeInTheDocument();
    expect(screen.getByText("Body text.")).toBeInTheDocument();
  });
});
