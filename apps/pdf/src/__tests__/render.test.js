import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { test } from "node:test";

import { chromium } from "playwright";

import { renderReportHtml } from "../template.js";
import { resolveLaunchOptions } from "../chromium-path.js";

const LAUNCH_OPTIONS = resolveLaunchOptions(existsSync);

const SAMPLE_REPORT = {
  report_type: "QUICK",
  language: "de",
  calculation_version: "1.0.0",
  knowledge_version: "1.0.0",
  prompt_version: "numra-report-v1",
  model_provider: "mock",
  model_name: "mock-v1",
  total_word_count: 120,
  sections: [
    { section_id: "executive_profile", title: "Executive Profile", order_index: 0, text: "Erste Absatz.\n\nZweiter Absatz.", word_count: 60, summary: "s" },
    { section_id: "life_path", title: "Life Path", order_index: 1, text: "Lebenszahl Text.", word_count: 60, summary: "s" },
  ],
};

const SAMPLE_PROFILE = {
  calculation_system: "numra-canonical",
  calculation_version: "1.0.0",
  core_numbers: {
    life_path: { display_value: "22/4", master_number: 22, flags: [] },
    expression: { display_value: "62/8", master_number: null, flags: [] },
    soul_urge: { display_value: "18/9", master_number: null, flags: [] },
    personality: { display_value: "44/8", master_number: null, flags: [] },
    birthday: { display_value: "18/9", master_number: null, flags: [] },
    attitude: { display_value: "25/7", master_number: null, flags: [] },
    maturity: { display_value: "12/3", master_number: null, flags: [] },
    balance: { display_value: "4", master_number: null, flags: [] },
  },
};

const SAMPLE_PERSON = { birth_first_names: "Lukas", birth_last_name: "Springer", birth_date: "1986-07-18" };

test("renderReportHtml includes cover, TOC, sections, and appendix", () => {
  const html = renderReportHtml({ report: SAMPLE_REPORT, profile: SAMPLE_PROFILE, person: SAMPLE_PERSON });
  assert.match(html, /Lukas Springer/);
  assert.match(html, /Executive Profile/);
  assert.match(html, /Life Path/);
  assert.match(html, /22\/4/);
  assert.match(html, /Calculation Appendix/);
  assert.match(html, /<html/);
});

test("renderReportHtml escapes untrusted-looking text content", () => {
  const report = {
    ...SAMPLE_REPORT,
    sections: [{ section_id: "x", title: "<script>evil()</script>", order_index: 0, text: "safe", word_count: 1, summary: "s" }],
  };
  const html = renderReportHtml({ report, profile: SAMPLE_PROFILE, person: SAMPLE_PERSON });
  assert.doesNotMatch(html, /<script>evil\(\)<\/script>/);
  assert.match(html, /&lt;script&gt;/);
});

test("full render pipeline produces a valid multi-page PDF with no runtime errors", async () => {
  const browser = await chromium.launch(LAUNCH_OPTIONS);
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(String(error)));

    const html = renderReportHtml({ report: SAMPLE_REPORT, profile: SAMPLE_PROFILE, person: SAMPLE_PERSON });
    await page.setContent(html, { waitUntil: "load" });

    assert.deepEqual(errors, []);

    const pdfBuffer = await page.pdf({ format: "A4", printBackground: true });

    assert.ok(pdfBuffer.length > 1000, "PDF buffer should be non-trivial in size");
    assert.equal(pdfBuffer.subarray(0, 5).toString("latin1"), "%PDF-");

    const pdfText = pdfBuffer.toString("latin1");
    const pageObjectMatches = pdfText.match(/\/Type\s*\/Page[^s]/g) || [];
    assert.ok(pageObjectMatches.length > 0, "PDF must contain at least one page object");
  } finally {
    await browser.close();
  }
});

test("key headings survive into the rendered page text", async () => {
  const browser = await chromium.launch(LAUNCH_OPTIONS);
  try {
    const page = await browser.newPage();
    const html = renderReportHtml({ report: SAMPLE_REPORT, profile: SAMPLE_PROFILE, person: SAMPLE_PERSON });
    await page.setContent(html, { waitUntil: "load" });

    const headings = await page.$$eval("h1, h2", (nodes) => nodes.map((n) => n.textContent));
    assert.ok(headings.some((h) => h.includes("Lukas Springer")));
    assert.ok(headings.some((h) => h.includes("Executive Profile")));
    assert.ok(headings.some((h) => h.includes("Calculation Appendix")));
  } finally {
    await browser.close();
  }
});
