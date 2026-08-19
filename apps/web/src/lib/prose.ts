/**
 * Splits a generated section's raw text into display paragraphs.
 *
 * Purely presentational: it never rewrites, trims down, summarises or reorders the
 * words the API returned — it only decides where a `<p>` boundary goes. Blank lines
 * are the primary separator; a text that uses single newlines as paragraph breaks
 * (no blank lines anywhere) falls back to splitting on those, so such a report reads
 * as paragraphs instead of one undifferentiated block.
 */
export function splitParagraphs(text: string): string[] {
  const normalized = text.replace(/\r\n/g, "\n").trim();
  if (normalized.length === 0) return [];

  const byBlankLine = normalized
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter((p) => p.length > 0);

  if (byBlankLine.length > 1) return byBlankLine;

  return normalized
    .split(/\n/)
    .map((p) => p.trim())
    .filter((p) => p.length > 0);
}
