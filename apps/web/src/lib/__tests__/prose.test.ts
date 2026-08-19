import { describe, expect, it } from "vitest";
import { splitParagraphs } from "@/lib/prose";

describe("splitParagraphs", () => {
  it("splits on blank lines", () => {
    expect(splitParagraphs("First para.\n\nSecond para.")).toEqual([
      "First para.",
      "Second para.",
    ]);
  });

  it("falls back to single newlines when the text has no blank lines", () => {
    expect(splitParagraphs("Line one.\nLine two.")).toEqual(["Line one.", "Line two."]);
  });

  it("keeps a single paragraph whole", () => {
    expect(splitParagraphs("Just one paragraph.")).toEqual(["Just one paragraph."]);
  });

  it("normalizes CRLF and drops empty runs", () => {
    expect(splitParagraphs("A.\r\n\r\n\r\nB.")).toEqual(["A.", "B."]);
  });

  it("returns nothing for empty or whitespace-only text", () => {
    expect(splitParagraphs("")).toEqual([]);
    expect(splitParagraphs("   \n  ")).toEqual([]);
  });

  it("never alters the words it returns", () => {
    const text = "The Life Path is 22/4.\n\nIt reduces from 22.";
    expect(splitParagraphs(text).join(" ")).toBe(
      "The Life Path is 22/4. It reduces from 22.",
    );
  });
});
