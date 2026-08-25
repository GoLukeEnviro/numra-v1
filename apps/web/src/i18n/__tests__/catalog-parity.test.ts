import { describe, expect, it } from "vitest";
import { CATALOG, SUPPORTED_LOCALES } from "@/i18n/catalog";
import { de } from "@/i18n/messages/de";
import { en } from "@/i18n/messages/en";

/**
 * The type system already forbids a missing or extra key in `en` (it is declared as
 * `Record<keyof typeof de, string>`), but it cannot catch an entry that exists and is
 * *empty* — an untranslated placeholder left behind mid-release would type-check and
 * then render as blank chrome. These assertions run against the real catalogs, so a
 * gap fails the suite rather than shipping.
 */
describe("i18n catalog parity", () => {
  const deKeys = Object.keys(de).sort();
  const enKeys = Object.keys(en).sort();

  it("has an identical key set in both locales", () => {
    expect(enKeys).toEqual(deKeys);
  });

  it("has no blank translation in any locale", () => {
    for (const locale of SUPPORTED_LOCALES) {
      const blank = Object.entries(CATALOG[locale])
        .filter(([, value]) => value.trim().length === 0)
        .map(([key]) => key);
      expect(blank, `blank ${locale} translations`).toEqual([]);
    }
  });

  it("never falls back to the German string for a translated English key", () => {
    // Proper nouns and language names are legitimately identical across locales;
    // everything else being byte-identical is the signature of a copy-paste stub.
    const ALLOWED_IDENTICAL = new Set([
      "settings.languageGerman",
      "settings.languageEnglish",
    ]);
    const suspicious = deKeys.filter(
      (key) =>
        !ALLOWED_IDENTICAL.has(key) &&
        de[key as keyof typeof de] === en[key as keyof typeof en] &&
        // Single tokens (numbers, brand words, "NUMRA", "PDF") are fine untranslated.
        de[key as keyof typeof de].trim().includes(" "),
    );
    expect(suspicious).toEqual([]);
  });
});
