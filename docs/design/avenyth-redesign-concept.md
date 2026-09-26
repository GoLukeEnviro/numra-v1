# AVENYTH Redesign-Konzept — Stufe 1 ausgearbeitet, Stufe 2 Skizze

**Status:** Entwurf, nicht mergen  
**Produktmarke:** AVENYTH  
**Namensraum:** NUMRA (technisch)  
**Stand:** 26.09.2026  
**Geprüfter Code:** `GoLukeEnviro/numra-v1` `main` @ `989c502`  
**Live-Stichprobe:** https://avenyth.de 26.09.2026 12:49 MESZ  
**Geltung:** nur Dokumentation unter `docs/design/**`. Kein App-Code, kein Live-Write, keine Änderung an `robots.txt`, `docs/adr/` oder `docs/brand/`.

Dieses Dokument ist ein Konzept, kein Abnahmebeleg und kein Beschluss über Stufe 2.

---

## 0 · Entscheidungstabelle

| Frage | Vorschlag | Status |
|---|---|---|
| Stufe 1 / Stufe 2 | Stufe 1 ausarbeiten. Stufe 2 nur Anhang A, nicht gebaut, nicht freigegeben | zur Freigabe |
| Pflaume | kein stiller Bugfix. Brand/Code-Konflikt mit Optionen A / B / C (Abschnitt 0.1) | **offen** |
| Schriften Welle 1 | System-Stack bleibt. Webfonts erst nach LCP-Messung an einem Beispielscreen | offen, mit Messplan |
| Heller Modus | nur Bericht-Reader, PDF-Innenseiten, Onboarding — nicht die ganze App | zur Freigabe |
| Richtungs-Schalter | keiner in Welle 1. Kein `UI_DIRECTION_DEFAULT` in Produktion vor Pflichtseiten und klarem Deploy-SHA | zur Freigabe |
| Primärbutton | keine Goldfläche (§3.2). Elfenbein-Fläche, Noir-Text; Gold nur Wert, aktiver Zustand, Fokus | zur Freigabe |
| Signatur | eine Zahl sieht aus wie eine Konstruktion. Graph zeichnet nur Allowlist-Operationen | zur Freigabe |

### 0.1 Pflaume-Konflikt — keine Bugfix-Lesart

**Beobachtung.** Brand `docs/brand/visual-identity.md` §3.2 (Stand 2026-09-09): *Pflaume markiert das Gemeinsame.* Gold markiert Beweis, nie Flächen.

**Beobachtung.** Code `apps/web/src/components/ui/badge.tsx` auf `989c502`:

- `private`: `bg-plum text-ivory` — Absicht laut Kommentar: AA-Paarung Fläche/Elfenbein (~6,44:1, nachgerechnet)
- `shared`: `border-gold/40 bg-gold/15 text-gold` — Absicht laut Kommentar: nicht mit `master` verwechseln
- `karmic`: ebenfalls Pflaume-Fläche

Das ist kein Versehen. Es ist ein Zielkonflikt zwischen Markensemantik und Kontrast/Unterscheidbarkeit.

| Option | Maßnahme | Folge |
|---|---|---|
| **A — Brand-treu** | Shared = Pflaume hell `#B39BCF` als Linie/Text plus Doppellinie. Private = neutraler Outline. Karmic bleibt Pflaume-Fläche oder bekommt eigenes Zeichen | Semantik und Logo stimmen. Shared verliert den stärksten Akzent |
| **B — Code nachziehen** | Brand §3.2 datiert ändern: Pflaume = Tiefe/Privat/Karma, Gold-Ton = geteilt | Dokument und UI stimmen. Logo-Knotenfarbe muss mit erklärt werden |
| **C — Trennen** | Shared bleibt Gold-Ton. Pflaume nur Logo-Querbalken und optionale Beziehungs-Linie. Private bleibt Outline | wenig Umbau. Semantik bleibt gespalten |

**Empfehlung:** Option A, erst nach Preview-Vergleich, nicht als stiller PR „Badge-Fix“.  
**Keine Umsetzung in diesem Docs-PR.**

---

## 0.2 Errata gegen den vorherigen Plan

| Nr | Frühere Aussage | Korrektur | Kennzeichnung |
|---|---|---|---|
| E1 | HSTS fehlt live | Live 12:49 MESZ: `strict-transport-security: max-age=31536000`. Offen: `/impressum` 404, `/datenschutz` 404, `robots.txt` `Disallow: /`, `x-powered-by: Next.js` | geprüft (Header) |
| E2 | Graph nur `segment_reduce` / `sum` / `reduce` | `trace.ts` kennt zusätzlich `letter_mapping`, `frequency_count`, `max_select`, `missing_values`, `distinct_count`. Diagnose: `digit_concat` | geprüft (Code) |
| E3 | `bg-white/12` erzeugt kein CSS | Tailwind 3 erlaubt Opacity auf `white`. Linie kann existieren und nur blass sein | Annahme |
| E4 | Preview sei privat | Repo ist öffentlich. `noindex` verhindert keinen GitHub-Abruf | geprüft |
| E5 | Heute-Kette als Engine-Fakt | Engine für Timing in diesem Lauf nicht ausgeführt | nicht geprüft |
| E6 | Produktion weit hinter main | `VERIFIED_PRODUCTION_SHA=78c87c94`. `989c502` ist docs-only danach | geprüft |
| E7 | Badge-Pflaume = Bugfix | siehe 0.1 | geprüft |

**Produkt-Reihenfolge:** Pflichtseiten und ehrliche öffentliche Fläche vor jeder sichtbaren UI-Welle.

---

## 1 · Ausgangslage und Befunde

### 1.1 Produkt und Stack

| Aussage | Quelle | Lage |
|---|---|---|
| Next.js 15.5, React 18.3, Tailwind 3.4 | `apps/web/package.json` @ `989c502` | `next ^15.5.24`, `react ^18.3.1`, `tailwindcss ^3.4.13` |
| `tailwind-merge ^3.7.0` | dieselbe Datei | eigener späterer PR, nicht dieser |
| `force-dynamic` | `apps/web/src/app/layout.tsx:9` | geprüft |
| `data-theme="dark"` hart | `layout.tsx` | Tailwind `darkMode: "class"` liest `.dark`, nicht `data-theme` |
| kein `error.tsx` / `not-found.tsx` auf `main` | Codesuche | 0 Treffer; Härtung auf anderem Branch |
| Mobile frozen | Execution-State | nicht Teil dieses Konzepts |

### 1.2 Tokens

12 Hex-Werte in `apps/web/tailwind.config.ts`: `background`, `surface`, `surface-2`, `gold`, `bronze`, `ivory`, `text`, `muted`, `plum`, `danger`, `danger-surface`, `success`. Kein CSS-Variablen-Satz. `border-white/10`-Zählung (~112) in diesem Lauf nicht per grep geprüft.

### 1.3 Duplikate

Hero / Auth-Shell / Fehlerbox / QuietState / Chat / Progress: Arbeitshypothese aus dem Vorgängerplan, hier nicht nachgezählt.

### 1.4 Kontrast (Skript `docs/design/tools/contrast_check.py`)

| Paar | Ratio | Note |
|---|---|---|
| Gold auf Noir | 8,74:1 | AA Text |
| Asche auf Noir | 7,00:1 | AA |
| Bronze auf Noir | 4,06:1 | nur Large / Deko |
| Pflaume auf Noir als Text | 2,57:1 | fail |
| Pflaume hell auf Noir | 7,96:1 | AA |
| Elfenbein auf Pflaume | 6,44:1 | AA auf Fläche |
| UI-Linie `#6B6775` auf Noir | 3,58:1 | AA-large / Rand |
| Tinte auf Papier | 14,54:1 | Lesemodus |

CVD Gold vs. Zinnober in diesem Lauf nicht nachgerechnet. Statusfarben immer Icon + Label.

### 1.5 Touchpoint-Brüche

| Stelle | Befund |
|---|---|
| PDF-Cover `template.js` `renderCoverPage` | kein Emblem, kein Profil-Hash; Eyebrow `AVENYTH — numra-canonical v…`; englische Tabelle |
| PDF-TOC | Überschrift `Contents` |
| Download | `numra-export-{id}.pdf` in `exports.py` |
| Web vs. PDF | Web Noir, PDF weiß/Georgia |

### 1.6 Live

Geprüft per Header 12:49 MESZ: Start 200, CSP `font-src 'self'`, HSTS gesetzt, `/impressum` 404, robots zu. Nicht geprüft: Chrome-Screenshots, LCP.

---

## 2 · Leitprinzip: Berechnung · Deutung · Reflexion

1. **Berechnung.** Eingaben, Operationen, Regelversion, `display_value`, Hash. Mono. Der Hash belegt Reproduzierbarkeit, nicht inhaltliche Wahrheit.
2. **Deutung.** Knowledge- und Composer-Text. Lesesatz. Disclaimer und `claim_class` bleiben sichtbar, wo das Produkt sie schon trägt.
3. **Reflexion.** Fragen, Journal, Check-in. Kein Score, keine Nähe-Metapher, keine Rohantworten der anderen Person.

P0: die Berechnungsebene sieht aus wie eine Konstruktion, nicht wie eine verzierte Zahl.

---

## 3 · Kritische Bewertung

1. Hoch — Versprechen unsichtbar: `trace-list.tsx` als Aufklapper. NumericWheel ist Dekor.
2. Hoch — Gold inflationär: `master`-Badge als Goldfläche, Shared als Gold-Ton. Widerspricht §3.2.
3. Mittel — kein Token-System. Drift bei Pflaume, `data-theme`, H1-Varianten.
4. Mittel — Lesbarkeit: oft 14 px, Bronze-Eyebrows 4,06:1, Versalien.
5. Mittel — Karten-Monotonie.
6. Mittel — IA: flache Sidebar, doppelte Beziehungseingänge, Dashboard/Heute, acht Tabs. Umbau ist Produkt-PR.
7. Hoch — Pflaume als Text 2,57:1.
8. Mittel — Copy: englische Labels, Rohcodes, PDF-Englisch.
9. Mittel — PDF bricht Brand §7.
10. Mittel — PhaseDisabled häufig, solange V2-Flags in Produktion aus sind.

Was hält: Markenwerte, Skip-Link/Fokus/`prefers-reduced-motion`, kein Kompatibilitäts-Score, Lesemaß 68ch, cva-Primitive.

---

## 4 · Stufe 1 „Noir, ruhiger“

Noir `#0B0B0F`, Gold `#C8A96B`, Pflaume `#604B72`, Logo bleiben. Gold nicht als Button-Füllung. Bronze nicht als Fließtext.

### 4.1 Additive Tokens

| Token | Hex | Kontrast auf Noir | Rolle |
|---|---|---|---|
| Pflaume hell | `#B39BCF` | 7,96:1 | Gemeinsames als Text/Linie, falls Option A |
| UI-Linie | `#6B6775` | 3,58:1 | Formularrand ≥ 3:1 |

Welle 1: Semantiknamen als Aliase über Ist-Hex, pixelgleich.

### 4.2 Heller Lesemodus „Tageslesung“

Nur Reader, PDF-Innenseite, Onboarding.

| Rolle | Hex | Kontrast |
|---|---|---|
| Papier | `#EEECF1` | — |
| Blatt | `#F8F7FA` | — |
| Tinte | `#1C1B24` | 14,54:1 auf Papier |
| Altgold | `#7A5B1F` | 5,35:1 |
| Pflaume | `#604B72` | 6,52:1 |
| Linie | `#827D8C` | 3,40:1 |

Kein App-weites Light-Theme in Welle 1.

### 4.3 Typo, Raster, Bewegung

Skala px: 12 · 14 · 16 · 18 · 21 · 24 · 36 · 48 · 72. UI-Text Ziel 16 px. Prosa 18 px / 1,65 / 66–68ch. Labels in Satzschreibung. Spacing-Basis 4 px. Grid 4 / 8 / 12, max 1200 px. Radius Control 6, Fläche 10, Sheet 16. Bewegung ≤ 240 ms / 4 px. Welle-1-Schriften: System-Stacks. Webfonts erst nach LCP, lokal, `font-src 'self'`.

---

## 5 · Signatur: Herleitung als Konstruktion

### 5.1 Trace-Vertrag (Entwurf)

Quelle: `metric.calculation_trace.operations` plus `metric.display_value`. Der Graph rechnet nicht.

**Allowlist:** `segment_reduce` (Eingangskette), `sum` (Operanden zum Summenknoten), `reduce` (gehaltene Kette).

**Kein Graph, Fallback `trace-list.tsx`:** `letter_mapping`, `frequency_count`, `max_select`, `missing_values`, `distinct_count`, `digit_concat`, unbekannter Typ.

Letzter sichtbarer Wert immer `metric.display_value`. Keine Frontend-Reduktion. Master nur 11 / 22 / 33, wenn `master_number` das trägt. Beziehungen: zwei Pfade, Querbalken mittendrin. Keine Prozentnähe.

### 5.2 Fiktives Beispiel

Nicht aus `fixtures/canonical/`. Demonstrator **12.06.1988**, von Hand nach `compute_life_path`:

- Tag 12 → 3
- Monat 6 → 6
- Jahr 1988 → 26 → 8
- Summe 3+6+8 = 17
- Reduktion 17 → 8

`display_value` setzt `reduce_compound`. Engine in diesem Lauf nicht ausgeführt. Timing-Kette (Canon §27–29) nicht geprüft, daher in der Preview keine erfundenen Zwischenwerte als Engine-Fakt. Verboten: `lukas-springer` und dessen Fixture-Datum.

---

## 6 · Komponenten und Tokens (Zielbild)

Welle 1 = Aliase auf Ist-Hex. Semantik: `canvas`, `surface`, `surface-raised`, `fg`, `fg-strong`, `fg-muted`, `line`, `line-control`, `accent` ≠ `evidence`, `shared`, `danger`, `success`, `ink` / `shade`.

Später: Switch, Checkbox, Sheet als `<dialog>`, NavTabs, InlineAlert, PageHeader, AuthShell, QuietState, JobProgress, ChatThread, PersonCard, DerivationGraph, ComparisonLedger ohne Summenzeile. RC2-Selektoren `role="switch"` und `aria-checked` bleiben.

---

## 7 · Screens

Navigation **Heute · Profile · Beziehungen · Berichte · Mehr** ist ein eigener Produkt-PR.

**Heute.** Eine Herleitungskette statt Riesenzahl plus Kacheln. Darunter Briefing in drei Ebenen.

**Bericht.** Lesemodus Tageslesung. Inhaltsverzeichnis. Provenance aus vorhandenen `metric_refs` / `knowledge_refs`. JobProgress als Stepper. Keine Rohcodes.

**Beziehungs-Workspace.** Header dauerhaft: Was teile ich gerade? DualColumn A | gemeinsam | B. Ledger ohne Gesamtwert. Check-in: `absolute_gap` und `direction` als Text, keine räumliche Nähe. Partnerantworten unsichtbar.

**Landing.** Nur Funktionen, die Produktion öffnet. Keine V2-Werbung bei ausgeschalteten Flags. Nur fiktive Beispiele.

**PDF (spätere Welle).** Deckblatt Brand §7: Emblem, Wortmarke, Hash in Mono, Goldlinie. Innenseiten Tageslesung. Deutsches Chrome. Dateiname `avenyth-report-*`.

---

## 8 · Spätere Umsetzung (nicht dieser PR)

CSS-Variablen `rgb(var(--x) / <alpha-value>)`. `tailwind-merge` 2.6-Linie als eigener PR. Fonts nach Messung. Tests: Typecheck, Lint, Vitest, E2E, Screenshot, axe zunächst nicht blockierend. PDF-Tokens mit `legacy`-Default.

---

## 9 · Rückfall

| Was | Rücknahme |
|---|---|
| Dieses Docs-Paket | PR schließen oder Commit revertieren |
| Spätere Token-Aliase | Screenshot gegen Legacy; Revert |
| Struktur (Nav, Graph, PageHeader) | nur Image oder Revert |
| Alias-Entfernung | erst nach Stufe-2-Entscheidung |

Kein Laufzeit-Schalter in Welle 1.

---

## 10 · Nächste Schritte

Außerhalb: Operator-Rechtstatsachen, dann `feat/legal-pages`. robots bleibt zu.

1. Dieses Dokument und die Preview reviewen; Pflaume A/B/C entscheiden.
2. Kleine Code-PRs später: Badge nur nach Beschluss, `bg-white/12` erst nach CSS-Beweis, PDF-Dateiname, Seitentitel, tailwind-merge.
3. Trace-Vertrag in `specs/` + fiktives Fixture, dann Graph nur auf „Heute“.
4. Token-Aliase pixelgleich.
5. Muster PageHeader / InlineAlert / Lesemodus.
6. Navigation als Produkt-PR.
7. Stufe 2 neu bewerten, wenn Stufe 1 sichtbar ist.

---

## Anhang A · Stufe 2 „Punkt und Linie“ — Skizze, nicht gebaut

**Status:** nicht freigegeben. Ultramarin statt Gold bricht Brand §3.2.

### A.1 Kandinsky (Tradition, nicht Engine-Kanon)

- Wassily Kandinsky, *Über das Geistige in der Kunst*, 1911/12.
- Wassily Kandinsky, *Punkt und Linie zu Fläche. Beitrag zur Analyse der malerischen Elemente*, München 1926, Bauhausbuch 9.

**Punkt.** Der geometrische Punkt ist unsichtbar und „gleicht einer Null“. In der Fläche wird er zur kleinsten Setzung: Ort, Ruhe, Konzentration. Neben einer Linie kippt derselbe Fleck zur Fläche.

**Linie.** „Spur des sich bewegenden Punktes“, entstanden durch Zerstörung der Ruhe des Punktes. Eine Kraft = Gerade. Wechselnde Kräfte = gebrochene Linie. Gleichzeitige Kräfte = Kurve.

**Fläche.** Grundfläche mit Spannung Zentrum/Rand (kühle Spannung zum Zentrum versus Auflösung).

**Farbe im früheren Text.** Blau zentripetal, Gelb zentrifugal. Das ist Malerei-Wirkungslehre, kein numerologisches Gesetz und kein AVENYTH-Claim.

Kandinsky sucht eine analytische Grammatik der Elemente, keine Ornamentlehre. Das ist der einzige übertragbare Satz.

### A.2 Nehmen / nicht nehmen

| Nehmen | Nicht nehmen |
|---|---|
| Punkt = gesetzter Wert / Knoten | „Geistige Notwendigkeit“ als Produktstimme |
| Linie = Operation | Farb-Ton-Synästhesie als Deutung |
| Fläche = ruhiger Lesekarton | Kreis-Dreieck-Quadrat als Dekor |
| Spannung Zentrum/Rand = Fokus auf den Summenknoten | Esoterik, Aura, Heilfarbe |
| Gerade = eine Kraft = eine Operation | Kunsthistorische Inszenierung der Marke |

Stufe 2 darf wie eine Konstruktion auf Karton wirken, nicht wie ein Bauhaus-Poster über Spiritualität.

### A.3 Skizzen-Palette

| Rolle | Hell | Dunkel |
|---|---|---|
| Grundfläche | Film `#ECEEE9` | `#14171D` |
| Text | Graphit `#22252A` (13,16:1) | Kreide |
| Beleg | Ultramarin `#2536A6` (8,33:1 auf Film) | `#9AA6FF` (8,67:1 auf Noir) |
| Gemeinsam | Ocker `#7C5A10` (5,40:1) plus Doppellinie | `#D6AA4E` |

CVD ΔE aus dem Vorgängerplan hier nicht erneut gemessen. Schriften der Skizze: Jost, Literata, IBM Plex Mono — nicht eingebaut. Verworfener Vorentwurf (Plex + Hellgrau + Blau) lag zu nah an Carbon.

### A.4 Mapping

Berechnung = Punkte und Linien (Ultramarin nur am Belegknoten). Deutung = Fläche ohne Akzent außer Provenance. Reflexion = zweite, schwächere Linie (Ocker), nie eine Zahl. Logo bleibt Noir-Kachel mit Goldlinien (Brand §2.6).

---

## Anhang B · Skills

Skills strukturieren die Arbeit. Belege stehen in Repo, Header und `contrast_check.py`. Nicht verfügbar in der Entstehungssitzung: Figma, lokaler Chrome, Live-Screenshots.

---

## Anhang C · Messprotokoll

```
python3 docs/design/tools/contrast_check.py
```

Ausgabe 26.09.2026: Abschnitt 1.4.

```
curl -sI https://avenyth.de/
```

12:49 MESZ: HTTP/2 200, HSTS `max-age=31536000`, CSP `font-src 'self'`, `x-powered-by: Next.js`.

```
curl -s -o /dev/null -w '%{http_code}' https://avenyth.de/impressum
```

404.

**Geprüft:** `989c502`, `tailwind.config.ts`, `badge.tsx`, `layout.tsx`, `package.json`, `trace.ts`, `date_metrics.py`, `exports.py`, `template.js`, `identity-timeline.tsx`, Live-Header, Execution-State #215.  
**Nicht geprüft:** grep-Zählungen, Chrome-Screenshots, Engine-Lauf der Beispielzahlen, CIE-ΔE, gebautes CSS für `bg-white/12`, V2-Flag-Werte live in diesem Lauf.

---

*Ende des Entwurfs. Keine der späteren Wellen ist durch dieses Dokument freigegeben.*
