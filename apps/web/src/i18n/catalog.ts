import { de } from "@/i18n/messages/de";
import { en } from "@/i18n/messages/en";

export type Locale = "de" | "en";
export const DEFAULT_LOCALE: Locale = "de";
export const SUPPORTED_LOCALES: readonly Locale[] = ["de", "en"];

export type MessageKey = keyof typeof de;

export const CATALOG: Record<Locale, Record<MessageKey, string>> = { de, en };

export function isLocale(value: string | null): value is Locale {
  return value === "de" || value === "en";
}
