import type { de } from "@/i18n/messages/de";

/**
 * English is switchable via Settings (V1.5 Epic G). Typed against `de`'s key set
 * so a missing/extra key fails `tsc`, not a runtime lookup.
 */
export const en: Record<keyof typeof de, string> = {
  "nav.today": "Today",
  "nav.dashboard": "Dashboard",
  "nav.people": "People",
  "nav.reports": "Reports",
  "nav.relationships": "Relationships",
  "nav.settings": "Settings",
  "nav.more": "More",
  "nav.logout": "Log out",
  "nav.newProfile": "New profile",
  "nav.primary": "Primary",

  "common.loading": "Loading…",
  "common.tryAgain": "Try again",
  "common.somethingWrong": "Something went wrong",

  "settings.title": "Settings",
  "settings.account": "Account",
  "settings.language": "Language",
  "settings.languageDescription": "The interface language. Reports and knowledge content are independent of this setting.",
  "settings.languageGerman": "Deutsch",
  "settings.languageEnglish": "English",
  "settings.privacyData": "Privacy & data",
  "settings.privacyDataDescription": "What Numra stores about you, and how to remove it.",
  "settings.viewPrivacySettings": "View privacy settings",
};
