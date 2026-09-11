# PR-WEB-07 — Evidence

Stand: Implementierung, lokale Prüfung und unabhängiger Review abgeschlossen;
PR-CI, Merge und Post-Merge-CI folgen.

## Umsetzung

- Neue Route und Navigation für Shared Tasks.
- Rollenrichtige Darstellung von Partner-Vorschlägen: Vorschlagende sehen den
  Wartezustand, Empfänger Annehmen/Ablehnen.
- Gemeinsame Aufgaben sind sofort aktiv; aktive Aufgaben können abgeschlossen
  oder archiviert werden.
- AVENYTH-Vorschläge werden eindeutig als solche gekennzeichnet und nicht
  automatisch aktiviert.
- DISSOLVED ist in der UI read-only; historische Aufgaben bleiben sichtbar.
- Archivierte und abgelehnte Aufgaben bleiben in einem eigenen Archiv sichtbar.
- Zustandsänderungen aktualisieren die Liste lokal, damit ein parallel geöffnetes
  Erstellungsformular samt Entwurf erhalten bleibt.
- Listen werden in 200er-Seiten vollständig geladen.

## Lokale Prüfungen

- `pnpm --filter @numra/web typecheck`: erfolgreich.
- `pnpm --filter @numra/web lint`: erfolgreich.
- `pnpm --filter @numra/web test`: 58 Dateien / 261 Tests erfolgreich.
- `pnpm --filter @numra/web build`: erfolgreich; Route
  `/workspaces/[id]/tasks` im Produktionsbuild enthalten.
- `pnpm exec playwright test pr-web-07-visual-baseline.spec.ts --config
  playwright.visual-baseline.config.ts`: 6/6 erfolgreich (aktive/eingehende
  Aufgaben, Erstellformular, DISSOLVED; Desktop und Mobile).
- Isolierte RC2-Journey gegen FastAPI/Postgres: Desktop und Mobile erfolgreich.
  Ein erster
  Mobile-Versuch lokalisierte per Trace eine von der festen Navigation verdeckte
  Playwright-Auto-Pointer-Aktion, bevor ein Accept-Request gesendet wurde. Der
  finale Nachweis klickt die gemessene Button-Mitte direkt und bestätigt auf
  beiden Viewports den Request, den gemeinsamen ACTIVE-Zustand und DISSOLVED.
- `numra-rc2`-Container, Volumes und Netzwerk anschließend vollständig entfernt.

## Unabhängiger Review

Vier P2-Befunde wurden behoben: Mobile-Pointer-Aussagekraft, fehlendes Archiv,
Verlust offener Erstellungsentwürfe und ein Workspace-Wechsel mit altem
Erfolgszustand. Das Abschluss-Re-Review fand keine verbleibenden Befunde.

## Review und CI

Wird nach Review/PR mit finalen Commit- und Run-Links ergänzt.
