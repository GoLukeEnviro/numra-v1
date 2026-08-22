/**
 * German is Numra's default UI language (V1.5 Epic G) -- this is the catalog
 * loaded when no locale preference has been chosen yet. Keys mirror en.ts 1:1;
 * `apps/web/src/i18n/catalog.ts` enforces that at the type level.
 */
export const de = {
  "nav.today": "Heute",
  "nav.dashboard": "Übersicht",
  "nav.people": "Personen",
  "nav.reports": "Berichte",
  "nav.relationships": "Beziehungen",
  "nav.settings": "Einstellungen",
  "nav.more": "Mehr",
  "nav.logout": "Abmelden",
  "nav.newProfile": "Neues Profil",
  "nav.primary": "Hauptnavigation",

  "common.loading": "Wird geladen…",
  "common.tryAgain": "Erneut versuchen",
  "common.somethingWrong": "Etwas ist schiefgelaufen",

  "settings.title": "Einstellungen",
  "settings.account": "Konto",
  "settings.language": "Sprache",
  "settings.languageDescription": "Sprache der Benutzeroberfläche. Berichte und Wissensinhalte sind hiervon unabhängig.",
  "settings.languageGerman": "Deutsch",
  "settings.languageEnglish": "English",
  "settings.privacyData": "Datenschutz & Daten",
  "settings.privacyDataDescription": "Was Numra über dich speichert und wie du es entfernst.",
  "settings.viewPrivacySettings": "Datenschutzeinstellungen ansehen",
} as const;
