# AVENYTH — Visuelle Identität

> Verbindliche Markenrichtlinie für alle Touchpoints (Web-App, PWA, PDF-Reports, Docs).
> Stand: 2026-09-09 · Version 2.0 · Quelle der Wahrheit: diese Datei + `apps/web/src/components/brand/logo.tsx` + `apps/web/src/lib/brand.ts`
>
> Ersetzt Version 1.0 ("Numra"). Numra war der Arbeitsname des Produkts bis
> PR-WEB-00B; er ist keine aktuelle Marke mehr und taucht in keinem
> nutzersichtbaren Text mehr auf (siehe `apps/web/src/__tests__/brand-guard.test.ts`).
> Rein technische Identifier (`@numra/web`, `@numra/pdf`, `@numra/schema`,
> `numra_api`, `numra_csrf`, LocalStorage-Keys, Cache-Namen,
> `numra-canonical`/`numra-report-v1`-Werte, DB-/Migrationsnamen) bleiben davon
> unberührt — sie sind interne Infrastruktur, keine Marke, und ein Wechsel dort
> wäre unnötiges Risiko ohne Nutzen (MINIMAL TOUCH).

---

## 1 · Markenkern

### 1.1 Was AVENYTH ist

AVENYTH ist ein **Personal + Relationship Development OS**: ein deterministisches
numerologisches Fundament (eine reine Python-Engine berechnet jeden Wert nach
dokumentierter Formel, `specs/canon-spec.md`) trägt sowohl die individuelle
Entwicklung einer Person als auch die gemeinsame Entwicklung von Beziehungen.
Ein LLM interpretiert ausschließlich, was die Engine bereits berechnet und
validiert hat — es erfindet nie einen Wert, nie einen Score, nie eine Zahl.
Die Marke muss dasselbe Versprechen tragen wie der Code:

> **„AVENYTH does not guess."**

### 1.2 Markenwerte

| Wert | Bedeutung | Gestalterische Konsequenz |
|---|---|---|
| **Determinismus** | Gleiche Eingabe → gleiches Ergebnis, gleicher Hash | Geometrische, konstruierte Formen; nichts Handgezeichnetes |
| **Transparenz** | Jede Zahl trägt ihre Herleitung | Traces sichtbar, Monospace für Belege |
| **Verbindung** | Individuelle und gemeinsame Entwicklung sind gleichrangig | Das Logo selbst zeigt zwei Wege, die sich mittendrin treffen |
| **Ruhe** | Deutung statt Aufregung | Dunkle Basis, ein Akzent, gedämpfte Bewegung |
| **Würde** | Kein Esoterik-Kitsch, kein Horoskop-Versprechen | Serif für Überschriften, Gold nur mit Bedeutung |

### 1.3 Positionierung

- **Konkurrenz:** bunte, verspielte Esoterik-Apps mit generischen Antworten,
  sowie Beziehungs-Apps, die Kompatibilität auf eine erfundene Prozentzahl
  reduzieren.
- **AVENYTH differenziert sich durch Ernsthaftigkeit auf zwei Ebenen zugleich:**
  dunkel, präzise, ruhig — und zwar sowohl für die einzelne Person (Personal
  Development) als auch für das Paar/die Beziehung (Relationship Development).
  Es gibt bewusst **keinen** kombinierten Kompatibilitäts-Score — ein Vergleich
  zeigt Unterschiede metrikweise, nicht als erfundene Gesamtzahl. Zielgruppe
  sind spirituell interessierte Menschen, die *Belege* statt Behauptungen
  wollen — für sich selbst und für ihre Beziehungen.

### 1.4 Tonalität (Brand Voice)

- Kurze Sätze im Indikativ. Erklären, nie behaupten.
- Keine Ausrufezeichen, keine Superlative, keine Vorhersagen.
- Leit-Claims (bereits auf der Login-Seite verankert):
  1. „Every number carries the trace that produced it."
  2. „The same inputs always reproduce the same hash."
  3. „No compatibility score is ever invented."

---

## 2 · Logo

### 2.1 Konzept: „Das konstruierte A"

Das Zeichen ist ein **A aus zwei divergierenden Beinen und einem Querbalken**,
konstruiert aus geraden Linien — dieselbe geometrische Grammatik wie zuvor das
"konstruierte N" (Numra: ein Buchstabe aus einem Numerologie-Knotennetz).
Markenkontinuität: Auch AVENYTHs Zeichen ist kein gezeichneter Schriftzug,
sondern ein aus Punkten und Linien **konstruierter** Buchstabe.

**Bedeutung:**
- Die **zwei divergierenden Beine** sind zwei Individuen bzw. zwei Pfade — sie
  starten an einem gemeinsamen Scheitelpunkt und laufen auseinander, jeder auf
  seiner eigenen Linie.
- Der **Querbalken** sitzt bei **~61 % der Höhe** — nicht am unteren Ende, wo
  sich die Beine träfen, sondern **mittendrin**. Das ist die zentrale Aussage
  des Zeichens: Der gemeinsame Beziehungsmoment entsteht *während* der
  Entwicklung, nicht erst als deren Ergebnis.
- Gleichzeitig ist das Zeichen unmissverständlich als Buchstabe **A** lesbar —
  die AVENYTH-Initiale.
- Die **Knoten am Scheitelpunkt und an den Fußpunkten** (Elfenbein) markieren
  Werte — Ausgangspunkt und Ziel jedes Pfads, nie Behauptungen.
- Die **Knoten auf dem Querbalken** (Pflaume `#604B72`) markieren den
  Beziehungsmoment selbst — bewusst in der Tiefenfarbe der Palette, nicht in
  Gold, um ihn von den individuellen Werten zu unterscheiden, ohne ihn
  abzuwerten.

### 2.2 Das Zeichen (Emblem)

Raster 32×32 · Scheitel 16/7 · Fußpunkte 9/25 und 23/25 · Querbalken
11,72/18 → 20,28/18 (≈ 61 % Höhe) · Strichstärke 1,4 · Gold `#C8A96B` auf
Noir `#0B0B0F` · Apex- und Fußknoten Elfenbein `#F2EBDD`, Radius 1,3 ·
Querbalken-Knoten Pflaume `#604B72`, Radius 1,6 · abgerundetes Quadrat,
Radius 7.

```
Linkes Bein      M16 7 → 9 25
Rechtes Bein     M16 7 → 23 25
Querbalken       M11.72 18 → 20.28 18
Apex-/Fußknoten  Scheitel (16,7), Fußpunkte (9,25) und (23,25) — Elfenbein
Beziehungsknoten Querbalken-Enden (11.72,18) und (20.28,18) — Pflaume
```

Kanonisches SVG: `apps/web/src/app/icon.svg`, synchron gehalten mit
`BrandMark` in `apps/web/src/components/brand/logo.tsx`.

### 2.3 Wortmarke

„AVENYTH" in der Serifen-Systemschrift (Georgia-Stack), Elfenbein. Als
Signatur folgt ein **goldener Punkt** — das Markenzeichen der Herleitung,
unverändert aus V1 übernommen.

### 2.4 Varianten

| Variante | Einsatz |
|---|---|
| Emblem (Gold auf Noir, gerundetes Quadrat) | App-Icon, Favicon, PWA-Icons |
| Emblem + Wortmarke („AVENYTH·") | Login, Sidebar, Report-Deckblätter |
| Wortmarke allein | Textkontexte, Footer |
| Monochrom (Elfenbein) | Druck, einfarbige Anwendungen |

### 2.5 Schutzraum & Mindestgrößen

- Schutzraum = Höhe eines Fußknotens (≥ 1/8 der Emblemhöhe) — kein Element näher.
- Emblem: mindestens **16 px** (Favicon-Größe), bevorzugt ≥ 24 px.
- Unter 16 px: Emblem ohne Knoten verwenden (reine A-Silhouette).

### 2.6 Fehlanwendungen (verboten)

- Farbe des Zeichens verändern (außer den definierten Varianten)
- Knoten entfernen, Linien krümmen oder Schatten hinzufügen
- Den Querbalken ans untere Ende verschieben (das widerspräche der Kernaussage:
  der Beziehungsmoment ist kein Endergebnis)
- Das Zeichen verzerren, rotieren oder mit Verläufen füllen
- Das Emblem auf unruhigen Hintergründen ohne Noir-Fläche platzieren

---

## 3 · Farbwelt

### 3.1 Palette (Design-Tokens in `apps/web/tailwind.config.ts`)

Unverändert aus V1 übernommen — die Palette trug bereits `plum`, das jetzt im
Logo eine tragende Rolle bekommt (Beziehungsknoten):

| Token | Name | HEX | Rolle |
|---|---|---|---|
| `background` | **Noir** | `#0B0B0F` | App-Hintergrund, Icon-Fläche |
| `surface` | **Obsidian** | `#13131A` | Karten, Sidebar |
| `surface-2` | **Obsidian+** | `#191921` | Erhöhte Flächen, Hover |
| `gold` | **Gold** | `#C8A96B` | Primärakzent — nur Bedeutung, nie Deko |
| `bronze` | **Bronze** | `#8F6B3E` | Sekundärlinien, Wheel-Ringe |
| `ivory` | **Elfenbein** | `#F2EBDD` | Überschriften, individuelle Knoten, Wortmarke |
| `text` | **Pergament** | `#E8E3D8` | Fließtext |
| `muted` | **Asche** | `#9E98A4` | Sekundärtext, Beschreibungen |
| `plum` | **Pflaume** | `#604B72` | Beziehungsknoten im Logo, tiefe Unterstützungsfarbe |
| `danger` | **Zinnober** | `#E28B7C` | Fehler, Zerstörung |
| `success` | **Salbei** | `#8FBF9F` | Erfolg, Bestätigung |

### 3.2 Regeln

- **Gold ist Beweis, nicht Verzierung.** Gold markiert Werte, aktive Zustände,
  den Fokusring und die Marke — nie Flächen.
- **Pflaume markiert das Gemeinsame.** Wo eine Ansicht zwei Personen
  zueinander in Beziehung setzt (Vergleichstabellen, geteilte Verbindungen),
  ist Pflaume der Akzent, der Individuelles (Gold/Elfenbein) von Gemeinsamem
  unterscheidet — konsistent mit dem Logo.
- Verhältnis ~90 % dunkle Flächen, ~7 % neutrale Texte, ~3 % Akzent (Gold,
  punktuell Pflaume).
- Verläufe nur als dezente Radial-Wäschen (`sacred-wheel-bg`), immer vom Gold
  ausgehend, nie mehr als 10 % Deckkraft.

---

## 4 · Typografie

### 4.1 Rollen

Unverändert aus V1:

| Rolle | Schrift | Einsatz |
|---|---|---|
| **Display/Serif** | System-Serif-Stack (Georgia) | Wortmarke, H1–H4, große Zahlenwerte |
| **UI/Sans** | System-Sans-Stack (Segoe UI u. a.) | Fließtext, Formulare, Navigation |
| **Beleg/Mono** | System-Mono-Stack | Hashes, Traces, Codes, Schritte |

Mono ist die **„Sprache der Verifikation"**: Alles, was nachweisbar ist
(Hashes, Trace-Schritte, Formelwerte), wird in Monospace gesetzt — sowohl für
individuelle Berechnungen als auch für Beziehungsvergleiche.

### 4.2 Skala

- H1 `text-4xl` Serif · H2 `text-2xl` · H3 `text-lg` · Body `text-sm` (UI) /
  `1.0625rem` mit `reading`-Maß (68ch) für Report-Prosa.

---

## 5 · Grafische Sprache

1. **Knoten & Linien** — Punkte markieren Werte, Hairlines verbinden sie.
2. **NumericWheel** — das 9-Knoten-Rad als dekoratives Sekundärmotiv,
   immer `aria-hidden`, nur in Deckkraft 20–40 %.
3. **Goldene Wäschen** — `sacred-wheel-bg` hinter Heroes, Lichtquelle konsistent
   von oben (bzw. oben links).
4. **Bewegung** — maximal `fade-in`/`rise-in` (200–240 ms, ≤ 4 px). Alles Größere
   wäre Dekoration auf einem Produkt, dessen Versprechen Nüchternheit ist.
   `prefers-reduced-motion` deaktiviert alles.

### 5.1 Private vs. gemeinsame Bildsprache

AVENYTH stellt visuell klar, ob eine Ansicht eine Person oder eine Beziehung
zwischen zwei Personen zeigt:

- **Private Ansichten** (ein Profil, eine Berechnung): Gold/Elfenbein als
  alleiniger Akzent, ein Knotenmotiv.
- **Geteilte Ansichten** (Vergleiche, Beziehungsmetriken): Pflaume tritt
  hinzu — nie als Ersatz für Gold, sondern als zweiter Akzent, der zeigt, dass
  hier zwei Werte nebeneinander stehen, ohne zu einer erfundenen Gesamtzahl
  verschmolzen zu werden (siehe `apps/web/src/components/relationships/comparison-table.tsx`,
  die explizit "kein Kompatibilitäts-Score" kommuniziert).

---

## 6 · Anwendung im Code

| Asset | Pfad |
|---|---|
| App-Icon/Favicon (SVG-Quelle) | `apps/web/src/app/icon.svg` |
| Emblem- + Logo-Komponente | `apps/web/src/components/brand/logo.tsx` |
| Frontend-Markenquelle (Name) | `apps/web/src/lib/brand.ts` (`BRAND_NAME`) |
| PWA-Icons (PNG) | `apps/web/public/icons/icon-*.png` |
| PWA-Manifest | `apps/web/public/manifest.webmanifest` |
| Farb-Tokens | `apps/web/tailwind.config.ts` |
| Globale Basis (Fokusring, Selektion, Wäschen) | `apps/web/src/app/globals.css` |
| Sekundärmotiv | `apps/web/src/components/layout/numeric-wheel.tsx` |
| Brand-Guard-Test (verhindert Rückfall auf "Numra") | `apps/web/src/__tests__/brand-guard.test.ts` |

### 6.1 PWA-Icons regenerieren

Nach jeder Änderung am Zeichen:

```bash
cd apps/web && node scripts/generate-brand-icons.mjs
```

Das Skript rendert `icon.svg` per Chromium in 192/512 px (sowie 512 px maskable
mit 20 % Sicherheitszone) und überschreibt die PNGs in `public/icons/`.

### 6.2 Backend-Markenwert

`GET /v1/public/config` liefert `app_name` aus `Settings.app_brand_name`
(`apps/api/src/numra_api/config.py`), Default `"AVENYTH"`. Das ist eine
bewusste, begrenzte Ausnahme für White-Label-Deployments — sie ist **nicht**
die Quelle der Frontend-Marke: `BRAND_NAME` in `apps/web/src/lib/brand.ts`
bleibt die einzige Wahrheit für UI-Text, Titel und Logo. Ein Integrationstest
(`apps/api/tests/integration/test_public_config.py::test_public_config_is_readable_without_any_cookie`)
prüft, dass der Backend-Default weiterhin `"AVENYTH"` ist, um Drift zwischen
Backend-Default und Frontend-Marke sichtbar zu machen.

---

## 7 · Report-Deckblätter (PDF)

Das PDF-Deckblatt (`apps/pdf/src/template.js`) verwendet: die Marke AVENYTH im
Cover-Eyebrow, Noir-Fläche, Elfenbein-Titel, eine goldene Hairline als
Trennlinie und den Profil-Hash in Monospace als Vertrauenssignatur. Die
technischen Werte `numra-canonical` (Calculation-System-Kennung) und
`numra-report-v1` (Prompt-Version) bleiben als interne Versionskennungen
unverändert — sie sind keine Marke, sondern Schema-/Prompt-Identifier.

---

*Die Marke AVENYTH verspricht dasselbe wie die Engine: nichts ist erfunden,
alles ist herleitbar — für eine Person allein und für zwei Personen
gemeinsam.*
