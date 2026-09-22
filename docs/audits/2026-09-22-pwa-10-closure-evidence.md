# PWA-10 — Abschluss-Nachweis (sanitisiert, versioniert)

- **Datum:** 2026-09-22
- **Audit-SHA:** `4b0926cdc9899cf652279d5ba909b05da68b3835` (Stack `numra-audit`, Parität
  datei-hashweise belegt: Python 10/10 identisch, Frontend-Build enthält die
  eingeführten Strings)
- **Rohbelege (Host, nicht im Repo):** `/home/hermes/nightrun/evidence/pwa06-reacceptance/`
  — `PWA10-CHECKS-*.json`, `PWA-06-REACCEPTANCE-20260921.md`,
  `PWA-10-GO-NOGO-20260921.md`; Rohdaten der Abnahme
  `pwa06-reaccept-20260921T172101Z.json/log`
- **Betriebsgrenzen:** nur synthetische `@example.com`-Konten; Produktion wurde nicht
  verändert (kein Deploy, keine Nutzerdaten)

## 1. Accessibility

Gemessen mit dem PWA-10-Sweep (Chromium, Desktop 1440×900 und Mobile 390×844):
eine sichtbare `h1` je Seite, `<main>`-Landmark vorhanden, `html lang="de"`, keine
Bilder ohne `alt`, keine Bedienelemente ohne zugänglichen Namen, kein positiver
`tabindex`.

| Seite | Desktop | Mobile 390px | vor dem Fix |
|---|---|---|---|
| `/` | PASS | PASS | — |
| `/register` | PASS | PASS | — |
| `/login` | PASS | PASS | mobil 0 sichtbare `h1` (#185) |
| `/forgot-password` | PASS | PASS | beide Viewports 0 `h1` (#185) |
| `/reset-password` | PASS | PASS | beide Viewports 0 `h1` (#185) |
| App (eingeloggt) | PASS | PASS | — |

Ursache und Fix: siehe #185 und PR #189 — die `h1` lag auf `/login` in einem
`hidden ... lg:block`-Panel und fehlte auf den beiden Passwortseiten ganz; sie steht
jetzt als `sr-only` außerhalb ausblendbarer Container. Gepinnt durch
`apps/web/src/app/__tests__/public-page-headings.test.tsx` (RED 3/4 → GREEN 4/4).

## 2. Performance

| Metrik | Wert |
|---|---|
| TTFB (Startseite / App) | 17 ms / 14 ms |
| Load (Startseite / App) | 137 ms / 109 ms |
| Kein horizontaler Overflow | Mobile ≤ 2 px auf beiden Flächen |

Methode: `performance.getEntriesByType("navigation")` im geladenen Dokument gegen den
Audit-Stack, keine synthetischen Werte, keine Lab-Bedingungen.

## 3. Install / Artefakte

| Prüfung | Ergebnis |
|---|---|
| `manifest.webmanifest` | 200 |
| `sw.js` | 200 |
| Icons (192/512) | 200 |
| Service Worker kontrolliert die Seite | ja |
| Statischer Precache offlin serviert | ja (`/manifest.webmanifest` über `force-cache`) |

## 4. Offline — akzeptierte Entscheidung, kein Mangel

```text
offline_page_controlled:               true
offline_static_precache_served:        true
offline_reload_ok:                     false   (erwartet)
offline_navigation_network_only:       true    (Entscheidung)
offline_no_stale_content:              true    (keine fremden Daten aus dem Cache)
```

Begründung und Konsequenzen: **ADR 014** (`docs/adr/014-offline-navigation-network-only.md`).
Gepinnt durch `apps/web/src/components/pwa/__tests__/sw-navigation-strategy.test.ts`.

## 5. Health-Smokes

| Umgebung | Ergebnis |
|---|---|
| Produktion (`:8443`, read-only) | Web 200, API `/v1/health/ready` `healthy` |
| Audit (`:8444`/`:17301`) | Web 200, API `healthy` |

## 6. Origin-Allowlist (#187)

| Prüfung | Ergebnis |
|---|---|
| Produktions-Origin gegen den echten Proxy | **401** `INVALID_CREDENTIALS` (Guard passiert, Auth greift) |
| Fremder Origin | **403** `ORIGIN_NOT_ALLOWED` |
| Produktions-`CORS_ALLOWED_ORIGINS` | `["https://agent0-1.taile6801f.ts.net:8443"]` — deckt die Web-Origin ab |

Die Prüfung ist als Schritt 7 in `docs/ops/release-verification.md` aufgenommen, damit
sie beim Produktions-Deploy erneut läuft und ein 403 auf der ersten Zeile als
Release-Blocker auffällt.

## 7. Was dieser Nachweis nicht behauptet

- **Kein Produktions-Deploy.** Der Audit-Stack wurde auf den Closure-SHA gebaut, die
  Produktion bleibt auf ihrem bisherigen Stand; der Deploy ist ein Operator-Gate.
- **Kein externer E-Mail-Versand** (#121): `avenyth.de` hat derzeit keine MX-Records,
  es existiert kein Provider/Postfach in irgendeiner Umgebung. Der Code- und
  SMTP-Transportpfad ist gegen einen Loopback-Sink bewiesen, die externe Zustellung
  nicht.
- **Der FAILED-Fall des Copilot ist test-belegt, nicht live erzwungen** — der Provider
  antwortete in jedem Lauf gültig; Renderer und korrigierender Retry sind durch Tests
  gepinnt (PR #183/#184).
