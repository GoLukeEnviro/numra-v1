# AVENYTH Redesign-Konzept — Stufe 1 ausgearbeitet, Stufe 2 Skizze

**Status:** Konzept, am 26.09.2026 nach `main` übernommen. Entscheidungen in §0, Pflaume offen (0.1). Kein App-Code freigegeben  
**Produktmarke:** AVENYTH  
**Namensraum:** NUMRA (technisch)  
**Stand:** 26.09.2026  
**Geprüfter Code:** `GoLukeEnviro/numra-v1` `main` @ `989c502` (seither nur `67de219`: `What's Next.txt`, ohne Einfluss)  
**Live-Stichprobe:** https://avenyth.de 26.09.2026 12:49 MESZ  
**Folge-Review:** 26.09.2026. Offene „nicht geprüft“-Punkte belegt (grep, Tailwind-Kompilat, Engine-Lauf, CVD), Entscheidungstabelle geschlossen, CI-Lint repariert (siehe E3, E5, E8, E9)  
**Geltung:** nur Dokumentation unter `docs/design/**`. Kein App-Code, kein Live-Write, keine Änderung an `robots.txt`, `docs/adr/` oder `docs/brand/`.

Dieses Dokument ist ein Konzept, kein Abnahmebeleg und kein Beschluss über Stufe 2.

---

## 0 · Entscheidungstabelle

| Frage | Beschluss | Status |
|---|---|---|
| Stufe 1 / Stufe 2 | Stufe 1 ausarbeiten. Stufe 2 nur Anhang A, nicht gebaut, nicht freigegeben | **freigegeben 26.09.2026** |
| Pflaume | kein stiller Bugfix. Brand/Code-Konflikt mit Optionen A / B / C (Abschnitt 0.1) | **offen, dokumentiert**. Entscheidung vor jedem Badge-PR |
| Schriften Welle 1 | System-Stack bleibt. Webfonts sind eine eigene, spätere Entscheidung nach LCP-Messung an einem Beispielscreen | **freigegeben 26.09.2026** (System-Stack) |
| Heller Modus | nur Bericht-Reader, PDF-Innenseiten, Onboarding, nicht die ganze App | **freigegeben 26.09.2026** |
| Richtungs-Schalter | keiner in Welle 1. Kein `UI_DIRECTION_DEFAULT` in Produktion vor Pflichtseiten und klarem Deploy-SHA | **freigegeben 26.09.2026** |
| Primärbutton | keine Goldfläche (§3.2). Elfenbein-Fläche, Noir-Text; Gold nur Wert, aktiver Zustand, Fokus. Wirkung auf Fläche in der Preview gezeigt (15,59:1 auf Obsidian, 14,72:1 auf Obsidian+) | **freigegeben 26.09.2026** |
| Signatur | eine Zahl sieht aus wie eine Konstruktion. Graph zeichnet nur Allowlist-Operationen (§5.1) | **freigegeben 26.09.2026** |

Freigabe heißt hier: Richtung des Konzepts. Keine dieser Zeilen gibt App-Code frei; jede spätere Welle ist ein eigener, kleiner PR nach den Pflichtseiten.

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

**Status 26.09.2026: offen, bewusst dokumentiert.**

- Bis zur Entscheidung gilt der heutige Code-Stand unverändert: `private`/`karmic` Pflaume-Fläche, `shared` Gold-Ton.
- Die Preview zeigt Option A nur zum Vergleich und ist dort so beschriftet.
- Messwerte für die Entscheidung:
  - Pflaume hell auf Noir 7,96:1
  - Elfenbein auf Pflaume 6,44:1
  - Pflaume als Text 2,57:1 (fail)
  - CVD Gold vs. Pflaume hell ΔE 15,3 (deutan), also unterscheidbar
- Auslöser für die Entscheidung: der erste Code-PR, der `badge.tsx` oder die Beziehungsansichten anfasst.

---

## 0.2 Errata gegen den vorherigen Plan

| Nr | Frühere Aussage | Korrektur | Kennzeichnung |
|---|---|---|---|
| E1 | HSTS fehlt live | Live 12:49 MESZ: `strict-transport-security: max-age=31536000`. Offen: `/impressum` 404, `/datenschutz` 404, `robots.txt` `Disallow: /`, `x-powered-by: Next.js` | geprüft (Header) |
| E2 | Graph nur `segment_reduce` / `sum` / `reduce` | `trace.ts` kennt zusätzlich `letter_mapping`, `frequency_count`, `max_select`, `missing_values`, `distinct_count`. Diagnose: `digit_concat` | geprüft (Code) |
| E3 | `bg-white/12` erzeugt kein CSS | **Bestätigt, die frühere Korrektur war falsch.** Tailwind **3.4.19** (Repo-Version) im Speicher kompiliert: `bg-white/10`, `bg-white/15`, `bg-white/[.12]` erzeugen CSS, `bg-white/12` **nicht**. Die Verbindungslinie in `identity-timeline.tsx:89` ist unsichtbar. Späterer Fix: `bg-white/[.12]` oder Token `line` | geprüft (Kompilat, Anhang C) |
| E4 | Preview sei privat | Repo ist öffentlich. `noindex` verhindert keinen GitHub-Abruf | geprüft |
| E5 | Heute-Kette als Engine-Fakt | **Jetzt per Engine gerechnet** (Quellen von `989c502`, Lauf lesend). Fiktiv 12.06.1988 am 26.09.2026: Universaljahr 10/1 → persönliches Jahr 10/1 → Monat 10/1 → Tag 9 | geprüft (Engine, Anhang C) |
| E6 | Produktion weit hinter main | `VERIFIED_PRODUCTION_SHA=78c87c94`. `989c502` ist docs-only danach | geprüft |
| E7 | Badge-Pflaume = Bugfix | siehe 0.1 | geprüft |
| E8 | Docs-only-PR berührt die CI nicht | **Falsch.** `lint-python` lief rot auf `bcfb1eb9`: `ruff I001` in `docs/design/tools/contrast_check.py:8` (zwei statt einer Leerzeile nach den Imports). `ruff check .` erfasst auch `docs/`. Im Folge-Commit behoben, lokal mit ruff 0.16.7 (CI-Version) geprüft | geprüft (CI-Log, ruff) |
| E9 | Stufe-2-Dunkelwerte „auf Noir“ | Falsche Basis. Die Skizze nutzt `#14171D`. Richtig: Ultramarin-dunkel 7,92:1, Ocker-dunkel 8,31:1, Kreide 14,32:1 | geprüft (Skript) |

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

12 Hex-Werte in `apps/web/tailwind.config.ts`: `background`, `surface`, `surface-2`, `gold`, `bronze`, `ivory`, `text`, `muted`, `plum`, `danger`, `danger-surface`, `success`. Kein CSS-Variablen-Satz.

Zählungen per grep über `apps/web/src` (`*.tsx`, `*.ts`), Befehle in Anhang C:

| Muster | Treffer |
|---|---|
| `border-white/10` | **112** |
| `text-sm` | **306** (UI-Text meist 14 px) |

### 1.3 Duplikate

| Muster | Beleg (grep) | Lesart |
|---|---|---|
| Hero mit `sacred-wheel-bg-left` | **6 Dateien**: dashboard, people/[id], analysis/[calculationId], relationships/[id], workspace-header, relationship-workspace-header | dazu eine Variante im Report-Reader |
| `function QuietState` | **3 Definitionen** (verify-email, reset-password, connections/redeem) | fast gleich zu `PhaseDisabledState` |
| `bg-danger-surface` | **26 Vorkommen in 24 Dateien** | umfasst das Inline-Fehlerbox-Muster plus Badge, Button und States. Die frühere Zahl „~22 Fehlerboxen“ ist eine Größenordnung, keine exakte Zählung |
| Auth-Shell, Chat, Progress | nicht erneut gezählt | Arbeitshypothese aus der Code-Analyse |

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
| UI-Linie auf Obsidian / Obsidian+ | 3,37:1 / 3,18:1 | Rand ≥ 3:1 auch auf Flächen |
| Elfenbein-Button auf Obsidian / Obsidian+ | 15,59:1 / 14,72:1 | Primärbutton als Fläche lesbar |
| Noir-Text auf Elfenbein-Button | 16,56:1 | AA |

**CVD** (dataviz-Validator, externes Skill-Skript, Eingaben in Anhang C):

| Paar | Wert | Folge |
|---|---|---|
| Gold vs. Zinnober | ΔE **3,4** (deutan), tritan 6,1 | für Deuteranope kaum unterscheidbar. Statusfarben immer mit Icon und Label |
| Beleg vs. Gemeinsam, Stufe 1 (Gold / Pflaume hell) | ΔE **15,3** (deutan) | trennbar |
| Beleg vs. Gemeinsam, Skizze Stufe 2 (Ultramarin / Ocker, hell) | ΔE **26,1** (protan) | deutlich trennbar |

Die Gesamtbewertung des Validators („FAILED“) betrifft Lightness-Band und Chroma-Floor für **Chart-Serien**. Diese Checks gelten nicht für UI-Rollen und sind hier nicht maßgeblich.

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

### 4.4 Stufe 1 gegen die Skizze Stufe 2

Grundlage: die Preview (`avenyth-redesign-preview.html`, Umschalter oben) mit identischem, fiktivem Inhalt in beiden Richtungen. **M** = gemessen, **U** = Urteil.

| Kriterium | Stufe 1 „Noir, ruhiger“ | Skizze Stufe 2 „Punkt und Linie“ |
|---|---|---|
| Markentreue | hält §2.6 und §3.2: Gold bleibt Belegfarbe, Pflaume bleibt im System (U) | bricht §3.2: Ultramarin ersetzt Gold als Beleg. Das Logo bleibt, steht aber farblich allein (U) |
| Grundwirkung | dunkel, ruhig, nah am heutigen Produkt; Risiko „generischer Premium-Dark-Look“ (U) | hell, konstruiert, eigenständiger; Risiko „kühl, technisch“ (U) |
| Text-Kontrast | Pergament auf Noir 15,35:1, Asche 7,00:1 (M) | Graphit auf Film 13,16:1, Blei 5,46:1 (M) |
| Beleg vs. Gemeinsam (CVD) | ΔE 15,3 (M) | ΔE 26,1 (M) |
| Langes Lesen | nur über den hellen Lesemodus (Reader, PDF) (U) | hell als Grundzustand; das PDF passt ohne Bruch (U) |
| Umbauumfang | Aliase über Ist-Hex, pixelgleich möglich (U) | neue Palette, neue Schriften, neue Doku-Grundlage (Brand §3) (U) |
| Rückfall | Image + Revert; Token-Aliase per Screenshot prüfbar (U) | erst nach eigener Markenentscheidung sinnvoll (U) |

**Lesart:** Stufe 1 ist der freigegebene Weg. Die Skizze bleibt ein Vergleichsmaßstab. Sie zeigt, was eine konstruierte, helle Fläche leisten würde. Neu bewertet wird sie erst, wenn Stufe 1 sichtbar ist.

---

## 5 · Signatur: Herleitung als Konstruktion

### 5.1 Trace-Vertrag (Entwurf)

Quelle: `metric.calculation_trace.operations` plus `metric.display_value`. Der Graph rechnet nicht.

**Allowlist:** `segment_reduce` (Eingangskette), `sum` (Operanden zum Summenknoten), `reduce` (gehaltene Kette).

**Kein Graph, Fallback `trace-list.tsx`:** `letter_mapping`, `frequency_count`, `max_select`, `missing_values`, `distinct_count`, `digit_concat`, unbekannter Typ.

Letzter sichtbarer Wert immer `metric.display_value`. Keine Frontend-Reduktion. Master nur 11 / 22 / 33, wenn `master_number` das trägt. Beziehungen: zwei Pfade, Querbalken mittendrin. Keine Prozentnähe.

### 5.2 Fiktives Beispiel

Nicht aus `fixtures/canonical/`. Demonstrator **12.06.1988**, Stichtag **26.09.2026**. Per Engine gerechnet: `numra_numerology` aus `989c502`, Lauf lesend, Befehl in Anhang C.

**Lebenszahl** (`compute_life_path`), Operationen `segment_reduce`×3, `sum`, `reduce`:

- Tag 12 → 3
- Monat 6 → 6
- Jahr 1988 → 26 → 8
- Summe 3+6+8 = 17
- `display_value` **17/8**

**Heute** (Canon §27–29, `timing/personal.py`), Operationen je `sum`, `reduce`:

| Schritt | Operanden | `display_value` |
|---|---|---|
| Universaljahr | 2+0+2+6 = 10 | **10/1** |
| Persönliches Jahr | Monat 6 + Tag 3 + Universaljahr 1 = 10 | **10/1** |
| Persönlicher Monat | 1 + Kalendermonat 9 = 10 | **10/1** |
| Persönlicher Tag | 1 + Kalendertag 26 → 8 = 9 | **9** |

Alle Operationen liegen in der Allowlist aus §5.1. Der Endknoten zeigt immer den `display_value` der Engine (17/8, 10/1, 9) und keine im Frontend reduzierte Zahl. Verboten bleiben die Golden-Fixture und deren Geburtsdatum.

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
2. Kleine Code-PRs später: Badge nur nach Pflaume-Beschluss, `bg-white/12` → `bg-white/[.12]` bzw. Token (CSS-Beweis liegt vor, E3), PDF-Dateiname, Seitentitel, tailwind-merge.
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

**Fläche.** Die Grundfläche als Träger mit inneren Spannungen. „Zentrum/Rand“ und „kühle Spannung zum Zentrum versus Auflösung“ sind **unsere Paraphrase** für die Gestaltung, keine zitierte Kandinsky-These. Ohne Seitenangabe wird das nicht als Quelle geführt.

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
| Grundfläche | Film `#ECEEE9` | Nacht `#14171D` |
| Text | Graphit `#22252A` (13,16:1) | Kreide `#E3E6E8` (14,32:1 auf Nacht) |
| Beleg | Ultramarin `#2536A6` (8,33:1 auf Film) | `#9AA6FF` (7,92:1 auf Nacht) |
| Gemeinsam | Ocker `#7C5A10` (5,40:1) plus Doppellinie | `#D6AA4E` (8,31:1 auf Nacht) |

CVD Beleg vs. Gemeinsam: ΔE 26,1 hell (protan), gemessen mit dem dataviz-Validator (§1.4). Schriften der Skizze: Jost, Literata, IBM Plex Mono, nicht eingebaut. Der verworfene Vorentwurf (Plex + Hellgrau + Blau) lag zu nah an IBM Carbon.

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

### C.1 Folge-Review 26.09.2026 (reproduzierbar)

**grep-Zählungen** (§1.2, §1.3), im Repo-Root:

```
cd apps/web/src
grep -rho 'border-white/10' --include=*.tsx --include=*.ts . | wc -l   # 112
grep -rho '\btext-sm\b' --include=*.tsx . | wc -l                      # 306
grep -rl 'sacred-wheel-bg-left' --include=*.tsx .                       # 6 Dateien
grep -rn 'function QuietState' --include=*.tsx .                        # 3
grep -rho 'bg-danger-surface' --include=*.tsx . | wc -l                 # 26 (in 24 Dateien)
```

**Tailwind-Kompilat** (E3). Braucht eine installierte Tailwind 3.4.19 (`pnpm install`). Läuft im Speicher und schreibt keine Datei:

```
node -e "
const postcss=require('postcss'); const tailwind=require('tailwindcss');
postcss([tailwind({content:[{raw:'bg-white/12 bg-white/10 bg-white/15 bg-white/[.12]'}],corePlugins:{preflight:false}})])
  .process('@tailwind utilities;',{from:undefined}).then(r=>console.log(r.css))"
```

Ergebnis: Regeln nur für `bg-white/10`, `bg-white/15`, `bg-white/[.12]`, **keine** für `bg-white/12`.

**Engine-Lauf** (E5, §5.2). Python 3.11 mit pydantic, z. B. die Projekt-venv nach `uv sync`. Kein Bytecode, keine Datei:

```
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/engine-numerology/src python - <<'EOF'
import datetime as dt
from numra_numerology.cycles.segments import compute_birth_segments
from numra_numerology.metrics.date_metrics import compute_life_path
from numra_numerology.timing.personal import (compute_universal_year, compute_personal_year,
    compute_personal_month, compute_personal_day)
seg = compute_birth_segments(dt.date(1988, 6, 12)); d = dt.date(2026, 9, 26)
print(compute_life_path(seg).display_value)                      # 17/8
uy = compute_universal_year(d.year); py = compute_personal_year(seg, uy)
pm = compute_personal_month(py, d.month); pd = compute_personal_day(pm, d.day)
print(uy.display_value, py.display_value, pm.display_value, pd.display_value)  # 10/1 10/1 10/1 9
EOF
```

**CVD** (§1.4). `validate_palette.js` aus dem dataviz-Skill. Das ist ein externes Skript und nicht im Repo:

```
node validate_palette.js "#C8A96B,#B39BCF,#E28B7C,#8FBF9F" --mode dark --surface "#13131A" --pairs all
node validate_palette.js "#C8A96B,#B39BCF" --mode dark --surface "#13131A"
node validate_palette.js "#2536A6,#7C5A10" --mode light --surface "#F7F8F4"
```

Ergebnisse:
- Gold ↔ Zinnober: ΔE 3,4 (deutan)
- Gold ↔ Pflaume hell: ΔE 15,3
- Ultramarin ↔ Ocker: ΔE 26,1

**ruff** (E8), CI-Version 0.16.7:

```
ruff check docs/design/tools/contrast_check.py
ruff format --check docs/design/tools/contrast_check.py
```

Beides grün nach dem Fix.

**Geprüft:**
- Code und Stand: `989c502`, `tailwind.config.ts`, `badge.tsx`, `layout.tsx`, `package.json`, `trace.ts`, `date_metrics.py`, `timing/personal.py`, `cycles/segments.py`, `exports.py`, `template.js`, `identity-timeline.tsx`
- Live-Header, Execution-State #215
- grep-Zählungen, Tailwind-Kompilat, Engine-Lauf, CVD-ΔE
- CI-Log `lint-python` auf `bcfb1eb9`

**Nicht geprüft:**
- Chrome-Screenshots und LCP (lokal kein Chrome)
- V2-Flag-Werte live
- Anzahl der Auth-Shell-, Chat- und Progress-Duplikate
- das gerenderte PDF: Die Hash-/Emblem-Aussage stützt sich auf den Quelltext `template.js`

---

*Ende des Entwurfs. Keine der späteren Wellen ist durch dieses Dokument freigegeben.*
