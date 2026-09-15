# @numra/mobile

**STATUS=FROZEN** (seit 2026-09-15)

**Grund:** Produktentscheidung — der kanonische AVENYTH-Client ist die
responsive Web-Anwendung (`apps/web`) inkl. installierbarer PWA
(Manifest, Icons, Service Worker bereits vorhanden). Es wird keine
zweite, eigenständige Android-/iOS-App gebaut. Details:
`docs/planning/avenyth-pwa-execution-state.md`.

**Konsequenzen:**

- Keine neue Feature-Entwicklung in diesem Paket.
- Die bereits abgeschlossene native Arbeit (MOBILE-12A Foundation,
  MOBILE-12B Bearer-Auth, MOBILE-12C Today/Daily-Brief) bleibt
  unverändert als historischer Stand erhalten — nicht gelöscht, nicht
  weiterentwickelt.
- Spätere Optionen (Archivieren, Löschen, Wiederbeleben) sind offen und
  nicht Teil des aktuellen Plans.

Fragen zum Stand: siehe `docs/planning/avenyth-web-execution-state.md`
(Abschnitt MOBILE-12A/B/C) für die historische Implementierung.
