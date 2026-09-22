# ADR 014 — Offline-Navigation bleibt Network-only (keine gecachte Anwendungsshell)

## Status

Accepted — 2026-09-22. Ersetzt keine frühere Entscheidung; formalisiert eine bisher nur
im Service-Worker-Quelltext begründete Praxis und entscheidet den in #186 aufgeworfenen
Punkt.

## Context

AVENYTH ist als installierbare PWA gebaut (`manifest.webmanifest`, Icons, Service Worker
und statische Assets werden vom Service Worker kontrolliert). Der PWA-10-Check auf dem
Audit-Stack (`4b0926cd`) hat gemessen:

```text
offline_page_controlled: true     # der Service Worker kontrolliert die Seite
offline_reload_ok:       false    # Navigation ohne Netz scheitert (net::ERR_FAILED)
offline_shows_shell:     false
```

Der Befund ist die Folge der bestehenden Implementierung in `apps/web/public/sw.js`:
Der Service Worker cached **ausschließlich** unveränderliche, versionierte statische
Assets (`/_next/static/`, `/icons/`, `/manifest.webmanifest`) plus den Manifest-Eintrag.
Seiten-Navigationen werden bewusst network-only behandelt; `/api/` wird gar nicht
angefasst (dort liegen session-authentifizierte Daten).

Damit stand die Frage, ob das fehlende Offline-Verhalten ein Mangel ist, der vor dem
Abschluss behoben werden muss, oder eine bewusste Produkteigenschaft.

## Decision

**Offline-Navigation bleibt network-only. Eine gecachte Anwendungsshell wird nicht
eingeführt.**

Begründung: AVENYTH-Seiten sind serverseitig gerendert und enthalten personenbezogene
Daten — Profile, Calculation-Traces, Beziehungs-Workspaces, Check-ins, Reports. Ein
Response-Cache für Navigationsanfragen würde diese Seiten im Browser speichern. Auf
einem gemeinsam genutzten Gerät (geteilter Laptop, Familien-Tablet, öffentlicher
Rechner) könnte ein späterer Besucher ohne Anmeldung oder mit einem anderen Konto die
gecachte Seite einer anderen Person angezeigt bekommen — ein Datenschutzdefekt, kein
Feature. Der Service Worker trägt diese Begründung im Quelltext und die Test-Suite
pinnt sie (`sw.test.ts` für den `/api/`-Bypass, `sw-navigation-strategy.test.ts` für
die Network-only-Navigation und die Cache-Allowlist).

Die Installierbarkeit bleibt vollständig erhalten: Manifest, Service Worker,
Precache der Icons und der statischen Assets funktionieren; ein Nutzer kann AVENYTH auf
den Home-Screen legen und von dort starten. Was fehlt, ist ausschließlich die
Offline-Anzeige von Seiten.

## Consequences

- `offline_reload_ok: false` ist **erwartetes Verhalten**, nicht ein Abnahmefehler. Der
  PWA-10-Check wertet es entsprechend und ein späterer "Offline-Support"-PR muss gegen
  diese ADR argumentieren, nicht gegen einen beiläufigen Test.
- Eine neutrale Offline-Seite (statisch, ohne Nutzerdaten, `offline.html` im Precache
  mit Navigation-Fallback nur für Fehlerfälle) bleibt ausdrücklich als **separate,
  spätere Arbeit** zulässig. Sie ist nicht Teil des Closure-umfangs von PWA-10, weil
  sie kein Abnahmekriterium erfüllt, das heute nicht erfüllt wäre.
- Wird die Anwendung in einer Umgebung mit getrennten Browserprofilen pro Nutzer
  betrieben (z. B. verwaltetes Managed-Gerät), kann die Entscheidung neu bewertet
  werden. Die Begründung hängt an der gemeinsamen Gerätenutzung, nicht an AVENYTH
  selbst.
