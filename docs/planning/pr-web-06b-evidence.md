# WEB-06b — Evidence

Stand: 2026-09-11, Implementierung in PR #55 gemergt und vollständig geprüft.

## Gelieferter Umfang

- Eigener Check-in-Tab mit leerem Zustand, bestätigtem Rundenstart, Snapshot-Formular,
  Wartezuständen, Analyse, eigenen unveränderlichen Antworten und vollständiger Historie.
- Stabile Idempotency-Keys für Start und Submit. Ein unklarer Submit friert den
  Originalrequest ausschließlich im Arbeitsspeicher ein, getrennt nach Nutzer,
  Workspace und Runde. Session Storage enthält nur Key und Round-ID.
- Fragenverwaltung für Erstellen, Bearbeiten, Deaktivieren und Reaktivieren;
  Konfiguration und Relationship-Type sind während offener Runden gesperrt.
- DISSOLVED ist read-only; ein fehlendes historisches Template wird als ehrlicher
  leerer Archivzustand behandelt.
- Analysefelder werden ohne Score oder Partner-Rohwerte dargestellt. Richtung,
  Evidenzbasis, fehlender Delta-Wert und Snapshot-Herkunft sind fachlich bezeichnet.

## Lokale Verifikation

- pnpm --filter @numra/web typecheck: erfolgreich.
- pnpm --filter @numra/web lint: erfolgreich, null Warnungen.
- pnpm --filter @numra/web test: 57 Dateien, 255 Tests erfolgreich.
- pnpm --filter @numra/web build: erfolgreicher Next.js-Produktionsbuild.
- Visuelle Playwright-Baseline: zwölf Zustände erfolgreich, je sechs bei
  1440×900 und 390×844.
- Isolierte reale RC2-Journey zweimal erfolgreich nach finalen UI- und Reviewfixes:
  Desktop und Mobile, zwei separate Konten, Startbestätigung, getrennte Abgaben,
  ANALYZED, Historie und DISSOLVED/read-only.
- Das Compose-Projekt numra-rc2 wurde jeweils samt eigenen Volumes und Netzwerk
  entfernt. Bestehende Standardcontainer blieben unberührt.

## Unabhängige Review

Die unabhängige Review fand zunächst neun konkrete Punkte zu Retry-Payload,
Reload-Reconciliation, historischer Semantik, löschbarer Beschreibung, eigenen
Antworten, Wartezuständen, Migrationsherkunft, Pagination und Startbestätigung.
Nach deren Behebung deckte der Re-Review noch Nutzer- und Rundengrenzen des
flüchtigen Payload-Caches auf. Der abschließende Nachreview meldete keine
verbleibenden Findings.

## CI und Merge

- Finaler PR-Head: `98986b782fd93195dd443b0b8433232975314938`.
- PR-CI
  [34540062199](https://github.com/GoLukeEnviro/numra-v1/actions/runs/34540062199) auf diesem exakten Head:
  alle zwölf Required Checks erfolgreich.
- Squash-Merge-Commit: `7e8a19247457deacb5ac62f6edbc9c65925f452e`.
- Getrennte Post-Merge-CI
  [34540846280](https://github.com/GoLukeEnviro/numra-v1/actions/runs/34540846280) auf diesem exakten
  Main-Commit: alle zwölf Required Checks erfolgreich.

Kein Deployment und keine Aktivierung eines Produktionsflags erfolgten.
