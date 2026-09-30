# ADR 016 — Design-Tokens und UI-Richtung (ENTWURF)

**Status:** Entwurf  
**Datum:** 2026-09-26  
**Ort:** `docs/design/` — wandert erst nach PO-Beschluss nach `docs/adr/016-design-tokens-and-ui-directions.md`  
**Betrifft:** `apps/web`, später `apps/pdf`  
**Nicht betroffen:** Engine, Canon-Formeln, Mobile, Live-Config, `robots.txt`

---

## Kontext

Die visuelle Identität steht in `docs/brand/visual-identity.md`. Die Farben liegen als 12 Hex-Literale in `apps/web/tailwind.config.ts`. `data-theme="dark"` wird gesetzt und von Tailwind nicht gelesen (`darkMode: "class"`). Gold wird als Fläche und als Beweisfarbe gleichzeitig verwendet. Pflaume ist im Brand „Gemeinsames“, im Badge-Code „privat/karmisch“.

Ein früherer Plan wollte drei UI-Richtungen × Themes zur Laufzeit. Das ist für Welle 1 abgelehnt.

## Entscheidung (vorgeschlagen, nicht in Kraft)

1. Semantische Tokens (`canvas`, `evidence`, `accent`, `shared`, …) als CSS-Variablen.
2. Welle 1 mappt sie 1:1 auf die heutigen Hex-Werte. Sichtbarer Unterschied = 0, nachgewiesen per Screenshot, nicht behauptet.
3. Kein Laufzeit-Schalter `data-direction` in Welle 1.
4. Heller Satz nur für Reader, PDF-Innenseite, Onboarding.
5. Stufe 2 („Punkt und Linie“) bleibt Skizze, bis Stufe 1 sichtbar und entschieden ist.
6. Pflaume-Semantik ist ein eigener Beschluss (Option A/B/C im Konzept), kein Bestandteil dieses ADR-Entwurfs.

## Folgen

- Tailwind bleibt 3.4; Farben über `rgb(var(--token) / <alpha-value>)`.
- Alte Namen (`gold`, `plum`, …) bleiben Aliase, bis eine spätere Welle sie entfernt.
- PDF liest später generierte Tokens mit Default `legacy`.
- Rückfall: Image + Revert. Cookie darf keinen erzwungenen Betriebsmodus überstimmen, falls je ein Schalter kommt.

## Verworfen

- Drei Richtungen in Produktion.
- Goldflächen als Primärbutton.
- Webfonts vor LCP-Messung.
- Graph, der Operationstypen außerhalb der Allowlist zu Kanten macht.

## Offene Fragen an die projektverantwortliche Person

1. Pflaume Option A, B oder C?
2. ADR nach `docs/adr/` heben — ja/nein, Datum?
3. Token-Welle erst nach Pflichtseiten — bestätigt?
