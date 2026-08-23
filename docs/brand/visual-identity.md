# Numra — Visuelle Identität

> Verbindliche Markenrichtlinie für alle Touchpoints (Web-App, PWA, PDF-Reports, Docs).
> Stand: 2026-08-23 · Version 1.0 · Quelle der Wahrheit: diese Datei + `apps/web/src/components/brand/logo.tsx`

---

## 1 · Markenkern

### 1.1 Was Numra ist

Numra ist eine **deterministische, auditierbare Numerologie-Plattform**: Eine
reine Python-Engine berechnet jeden Wert nach dokumentierter Formel
(`specs/canon-spec.md`), ein LLM erklärt nur, was die Engine bereits erzeugt hat.
Die Marke muss dasselbe Versprechen tragen wie der Code:

> **„NUMRA does not guess."**

### 1.2 Markenwerte

| Wert | Bedeutung | Gestalterische Konsequenz |
|---|---|---|
| **Determinismus** | Gleiche Eingabe → gleiches Ergebnis, gleicher Hash | Geometrische, konstruierte Formen; nichts Handgezeichnetes |
| **Transparenz** | Jede Zahl trägt ihre Herleitung | Traces sichtbar, Monospace für Belege |
| **Ruhe** | Deutung statt Aufregung | Dunkle Basis, ein Akzent, gedämpfte Bewegung |
| **Würde** | Kein Esoterik-Kitsch, kein Horoskop-Versprechen | Serif für Überschriften, Gold nur mit Bedeutung |

### 1.3 Positionierung

- **Konkurrenz:** bunte, verspielte Esoterik-Apps mit generischen Antworten.
- **Numra differenziert sich durch Ernsthaftigkeit:** dunkel, präzise, ruhig —
  „die Uhr unter den Orakeln". Zielgruppe sind spirituell interessierte Menschen,
  die *Belege* statt Behauptungen wollen.

### 1.4 Tonalität (Brand Voice)

- Kurze Sätze im Indikativ. Erklären, nie behaupten.
- Keine Ausrufezeichen, keine Superlative, keine Vorhersagen.
- Leit-Claims (bereits auf der Login-Seite verankert):
  1. „Every number carries the trace that produced it."
  2. „The same inputs always reproduce the same hash."
  3. „No compatibility score is ever invented."

---

## 2 · Logo

### 2.1 Konzept: „Das konstruierte N" (N-Knoten)

Das Zeichen ist ein **N aus drei geraden Linien**, das an seinen vier Endpunkten
in **Knoten** (kleine Elfenbein-Punkte) mündet.

**Bedeutung:**
- Die **Linien** sind Ableitungen — jede Verbindung ist gerade, exakt, reproduzierbar.
- Die **Knoten** sind Werte — Eingabe und Ergebnis, nie Behauptungen.
- Das N selbst ist **geometrisch konstruierbar** (alle Koordinaten ganzzahlig
  ableitbar): Das Logo verkörpert die Markenphilosophie — nichts ist gezeichnet,
  alles ist konstruiert.
- Die Diagonale ist der **Weg** von der Eingabe zur Deutung.

Das Sekundärmotiv **NumericWheel** (9 Knoten der Pythagoreischen Zahlen) trägt
dieselbe Grammatik: Knoten + feine Verbindungslinien.

### 2.2 Das Zeichen (Emblem)

Raster 32×32 · Ecke 10,5/10,5 bis 21,5/21,5 · Strichstärke 2 · Gold `#C8A96B`
auf Noir `#0B0B0F` · Knoten Elfenbein `#F2EBDD`, Radius 1,6 · abgerundetes
Quadrat, Radius 7.

```
Links vertikal   M10.5 21.5 → 10.5 10.5
Diagonale        M10.5 10.5 → 21.5 21.5
Rechts vertikal  M21.5 10.5 → 21.5 21.5
Knoten           an allen vier Endpunkten
```

### 2.3 Wortmarke

„Numra" in der Serifen-Systemschrift (Georgia-Stack), Elfenbein. Als Signatur
folgt ein **goldener Knotenpunkt** (Punkt) — das Markenzeichen der Herleitung.

### 2.4 Varianten

| Variante | Einsatz |
|---|---|
| Emblem (Gold auf Noir, gerundetes Quadrat) | App-Icon, Favicon, PWA-Icons |
| Emblem + Wortmarke („Numra·") | Login, Sidebar, Report-Deckblätter |
| Wortmarke allein | Textkontexte, Footer |
| Monochrom (Elfenbein) | Druck, einfarbige Anwendungen |

### 2.5 Schutzraum & Mindestgrößen

- Schutzraum = Höhe des Knotenpunkts (≥ 1/8 der Emblemhöhe) — kein Element näher.
- Emblem: mindestens **16 px** (Favicon-Größe), bevorzugt ≥ 24 px.
- Unter 16 px: Emblem ohne Knoten verwenden (reine N-Silhouette).

### 2.6 Fehlanwendungen (verboten)

- Farbe des Zeichens verändern (außer den definierten Varianten)
- Knoten entfernen, Linien krümmen oder Schatten hinzufügen
- Das Zeichen verzerren, rotieren oder mit Verläufen füllen
- Das Emblem auf unruhigen Hintergründen ohne Noir-Fläche platzieren

---

## 3 · Farbwelt

### 3.1 Palette (Design-Tokens in `apps/web/tailwind.config.ts`)

| Token | Name | HEX | Rolle |
|---|---|---|---|
| `background` | **Noir** | `#0B0B0F` | App-Hintergrund, Icon-Fläche |
| `surface` | **Obsidian** | `#13131A` | Karten, Sidebar |
| `surface-2` | **Obsidian+** | `#191921` | Erhöhte Flächen, Hover |
| `gold` | **Gold** | `#C8A96B` | Primärakzent — nur Bedeutung, nie Deko |
| `bronze` | **Bronze** | `#8F6B3E` | Sekundärlinien, Wheel-Ringe |
| `ivory` | **Elfenbein** | `#F2EBDD` | Überschriften, Knoten, Wortmarke |
| `text` | **Pergament** | `#E8E3D8` | Fließtext |
| `muted` | **Asche** | `#9E98A4` | Sekundärtext, Beschreibungen |
| `plum` | **Pflaume** | `#604B72` | Tiefe Unterstützungsfarbe |
| `danger` | **Zinnober** | `#E28B7C` | Fehler, Zerstörung |
| `success` | **Salbei** | `#8FBF9F` | Erfolg, Bestätigung |

### 3.2 Regeln

- **Gold ist Beweis, nicht Verzierung.** Gold markiert Werte, aktive Zustände,
  den Fokusring und die Marke — nie Flächen.
- Verhältnis ~90 % dunkle Flächen, ~7 % neutrale Texte, ~3 % Gold.
- Verläufe nur als dezente Radial-Wäschen (`sacred-wheel-bg`), immer vom Gold
  ausgehend, nie mehr als 10 % Deckkraft.

---

## 4 · Typografie

### 4.1 Rollen

| Rolle | Schrift | Einsatz |
|---|---|---|
| **Display/Serif** | System-Serif-Stack (Georgia) | Wortmarke, H1–H4, große Zahlenwerte |
| **UI/Sans** | System-Sans-Stack (Segoe UI u. a.) | Fließtext, Formulare, Navigation |
| **Beleg/Mono** | System-Mono-Stack | Hashes, Traces, Codes, Schritte |

Mono ist die **„Sprache der Verifikation"**: Alles, was nachweisbar ist
(Hashes, Trace-Schritte, Formelwerte), wird in Monospace gesetzt.

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

---

## 6 · Anwendung im Code

| Asset | Pfad |
|---|---|
| App-Icon/Favicon (SVG-Quelle) | `apps/web/src/app/icon.svg` |
| Emblem- + Logo-Komponente | `apps/web/src/components/brand/logo.tsx` |
| PWA-Icons (PNG) | `apps/web/public/icons/icon-*.png` |
| Farb-Tokens | `apps/web/tailwind.config.ts` |
| Globale Basis (Fokusring, Selektion, Wäschen) | `apps/web/src/app/globals.css` |
| Sekundärmotiv | `apps/web/src/components/layout/numeric-wheel.tsx` |

### 6.1 PWA-Icons regenerieren

Nach jeder Änderung am Zeichen:

```bash
cd apps/web && node scripts/generate-brand-icons.mjs
```

Das Skript rendert `icon.svg` per Chromium in 192/512 px (sowie 512 px maskable
mit 20 % Sicherheitszone) und überschreibt die PNGs in `public/icons/`.

---

## 7 · Report-Deckblätter (PDF)

Das PDF-Deckblatt verwendet: Wortmarke mit Knoten, Noir-Fläche, Elfenbein-Titel,
eine goldene Hairline als Trennlinie und den Profil-Hash in Monospace als
Vertrauenssignatur.

---

*Die Marke Numra verspricht dasselbe wie die Engine: nichts ist erfunden, alles ist herleitbar.*
