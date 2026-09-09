import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

// Technische Identifier wie `numra_api`, `numra_csrf`, `@numra/web`,
// `@numra/pdf`, `@numra/schema`, `numra-canonical` sind durchgehend
// kleingeschrieben. Die Wortgrenzen-Regex `\bNumra\b` / `\bNUMRA\b` matcht
// nur groß-/gemischtgeschriebene Vorkommen, daher werden diese Identifier
// nie getroffen — eine Allowlist-Struktur ist nicht erforderlich.
const BRAND_PATTERN = /\bNumra\b|\bNUMRA\b/g;

const WEB_SRC_ROOT = join(__dirname, "..");
const WEB_SRC_EXTENSIONS = [".ts", ".tsx", ".svg"];
const WEB_EXCLUDED_DIRS = ["__tests__"];

const MANIFEST_PATH = join(__dirname, "..", "..", "public", "manifest.webmanifest");
const PDF_TEMPLATE_PATH = join(__dirname, "..", "..", "..", "pdf", "src", "template.js");

interface BrandMatch {
  file: string;
  line: number;
  text: string;
}

function collectWebSrcFiles(dir: string): string[] {
  const entries = readdirSync(dir);
  const files: string[] = [];

  for (const entry of entries) {
    if (WEB_EXCLUDED_DIRS.includes(entry)) continue;

    const fullPath = join(dir, entry);
    const stats = statSync(fullPath);

    if (stats.isDirectory()) {
      files.push(...collectWebSrcFiles(fullPath));
    } else if (WEB_SRC_EXTENSIONS.some((ext) => entry.endsWith(ext))) {
      files.push(fullPath);
    }
  }

  return files;
}

function findBrandMatches(filePath: string, displayPath: string): BrandMatch[] {
  const content = readFileSync(filePath, "utf-8");
  const lines = content.split("\n");
  const matches: BrandMatch[] = [];

  lines.forEach((line, index) => {
    const lineMatches = line.match(BRAND_PATTERN);
    if (lineMatches) {
      matches.push({ file: displayPath, line: index + 1, text: line.trim() });
    }
  });

  return matches;
}

describe("brand-guard", () => {
  it("enthält keine Display-Marke Numra/NUMRA in apps/web/src, manifest.webmanifest oder apps/pdf/src/template.js", () => {
    const scanTargets: Array<{ path: string; displayPath: string }> = [
      ...collectWebSrcFiles(WEB_SRC_ROOT).map((path) => ({
        path,
        displayPath: `apps/web/src/${relative(WEB_SRC_ROOT, path).split("\\").join("/")}`,
      })),
      { path: MANIFEST_PATH, displayPath: "apps/web/public/manifest.webmanifest" },
      { path: PDF_TEMPLATE_PATH, displayPath: "apps/pdf/src/template.js" },
    ];

    const allMatches = scanTargets.flatMap(({ path, displayPath }) =>
      findBrandMatches(path, displayPath),
    );

    const report = allMatches
      .map((match) => `${match.file}:${match.line}:${match.text}`)
      .join("\n");

    expect(allMatches, `Gefundene Brand-Lecks:\n${report}`).toEqual([]);
  });
});
