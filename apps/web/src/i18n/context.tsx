"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { CATALOG, DEFAULT_LOCALE, isLocale, type Locale, type MessageKey } from "@/i18n/catalog";

const LOCALE_KEY = "numra:locale:v1";

function readStoredLocale(): Locale {
  if (typeof window === "undefined") return DEFAULT_LOCALE;
  try {
    const stored = window.localStorage.getItem(LOCALE_KEY);
    return isLocale(stored) ? stored : DEFAULT_LOCALE;
  } catch {
    return DEFAULT_LOCALE;
  }
}

function writeStoredLocale(locale: Locale): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(LOCALE_KEY, locale);
  } catch {
    // Storage unavailable (private browsing, quota) — the choice just won't persist.
  }
}

interface LocaleContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: MessageKey) => string;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

/**
 * V1.5 Epic G: German is the default UI language; the choice is a per-browser
 * preference (like local-preferences.ts), not server state, since it only ever
 * changes how chrome renders, never what a calculation or report says. Interpretive
 * knowledge/report language is a separate, independent axis (currently German-only
 * content) — this provider only ever governs interface copy from the catalog.
 */
export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    const stored = readStoredLocale();
    setLocaleState(stored);
    document.documentElement.lang = stored;
  }, []);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    writeStoredLocale(next);
    document.documentElement.lang = next;
  }, []);

  const t = useCallback((key: MessageKey) => CATALOG[locale][key], [locale]);

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale(): LocaleContextValue {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useLocale must be used within a LocaleProvider");
  return ctx;
}
