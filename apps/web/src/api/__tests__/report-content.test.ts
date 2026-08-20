import { describe, expect, it } from "vitest";
import { asStructuredReport, orderedSections } from "@/api/report-content";

const section = (id: string, order: number) => ({
  section_id: id,
  title: `Section ${id}`,
  order_index: order,
  text: "Body text.",
  word_count: 2,
  summary: "",
});

const validContent = {
  report_type: "FULL",
  language: "de",
  calculation_version: "1.0.0",
  knowledge_version: "de-v1",
  prompt_version: "1",
  model_provider: "mock",
  model_name: "mock-1",
  total_word_count: 4,
  sections: [section("b", 1), section("a", 0)],
};

describe("asStructuredReport", () => {
  it("accepts a payload shaped like StructuredReport", () => {
    expect(asStructuredReport(validContent)).not.toBeNull();
  });

  it("rejects null content — a report still generating has none", () => {
    expect(asStructuredReport(null)).toBeNull();
  });

  it("rejects a payload without sections rather than rendering a blank report", () => {
    const { sections: _sections, ...withoutSections } = validContent;
    expect(asStructuredReport(withoutSections)).toBeNull();
  });

  it("rejects a payload whose sections are malformed", () => {
    expect(
      asStructuredReport({ ...validContent, sections: [{ section_id: "a" }] }),
    ).toBeNull();
  });
});

describe("orderedSections", () => {
  it("orders strictly by order_index", () => {
    const content = asStructuredReport(validContent);
    expect(content).not.toBeNull();
    expect(orderedSections(content!).map((s) => s.section_id)).toEqual(["a", "b"]);
  });

  it("does not mutate the payload the API returned", () => {
    const content = asStructuredReport(validContent);
    orderedSections(content!);
    expect(content!.sections.map((s) => s.section_id)).toEqual(["b", "a"]);
  });
});
