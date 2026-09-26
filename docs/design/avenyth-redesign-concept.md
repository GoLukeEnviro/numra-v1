# AVENYTH Redesign-Konzept — Stufe 1 ausgearbeitet, Stufe 2 Skizze

**Status:** Entwurf, nicht mergen  
**Produktmarke:** AVENYTH  
**Namensraum:** NUMRA (technisch)  
**Stand:** 26.09.2026  
**Geprüfter Code:** `GoLukeEnviro/numra-v1` `main` @ `989c502`  
**Live-Stichprobe:** https://avenyth.de 26.09.2026 12:49 MESZ  
**Geltung:** nur Dokumentation unter `docs/design/**`. Kein App-Code, kein Live-Write, keine Änderung an `robots.txt`, `docs/adr/` oder `docs/brand/`.

Dieses Dokument ist ein Konzept, kein Abnahmebeleg und kein Beschluss über Stufe 2.

Siehe Arbeitskopie im Projektordner `artifacts/docs/design/avenyth-redesign-concept.md` falls dieser Commit gekürzt wirken sollte. Volltext folgt.

---

## 0 · Entscheidungstabelle

| Frage | Vorschlag | Status |
|---|---|---|
| Stufe 1 / Stufe 2 | Stufe 1 ausarbeiten. Stufe 2 nur Anhang A, nicht gebaut, nicht freigegeben | zur Freigabe |
| Pflaume | kein stiller Bugfix. Brand/Code-Konflikt mit Optionen A / B / C (Abschnitt 0.1) | **offen** |
| Schriften Welle 1 | System-Stack bleibt. Webfonts erst nach LCP-Messung | offen |
| Heller Modus | nur Bericht-Reader, PDF-Innenseiten, Onboarding | zur Freigabe |
| Richtungs-Schalter | keiner in Welle 1 | zur Freigabe |
| Primärbutton | keine Goldfläche. Elfenbein-Fläche, Noir-Text | zur Freigabe |
| Signatur | Zahl als Konstruktion. Graph nur Allowlist-Operationen | zur Freigabe |

### 0.1 Pflaume-Konflikt — keine Bugfix-Lesart

Brand §3.2: Pflaume = Gemeinsames. Code `badge.tsx`: `private` und `karmic` = Pflaume-Fläche, `shared` = Gold-Ton. Absicht laut Kommentar (AA + Unterscheidung zu master), kein Versehen.

| Option | Maßnahme | Folge |
|---|---|---|
| **A — Brand-treu** | Shared = Pflaume hell `#B39BCF` plus Doppellinie. Private = Outline | Semantik stimmt. Shared verliert Gold-Gewicht |
| **B — Code nachziehen** | Brand §3.2 datiert ändern | Doku und UI stimmen. Logo-Knoten erklären |
| **C — Trennen** | Shared bleibt Gold-Ton. Pflaume nur Logo-Querbalken | wenig Umbau. Semantik gespalten |

Empfehlung: A, nach Preview, kein stiller Badge-PR.

### 0.2 Errata

| Nr | Korrektur |
|---|---|
| E1 | HSTS live 12:49 MESZ gesetzt (`max-age=31536000`). Offen: `/impressum` 404, robots Disallow, `x-powered-by` |
| E2 | `trace.ts` kennt mehr als drei Op-Typen: `letter_mapping`, `frequency_count`, `max_select`, `missing_values`, `distinct_count`; Diagnose `digit_concat` |
| E3 | `bg-white/12` ist Annahme, kein Beweis für fehlendes CSS |
| E4 | Preview ist nicht privat (Repo öffentlich) |
| E5 | Timing-Kette nicht per Engine gerechnet |
| E6 | Produktion `78c87c94`; `989c502` docs-only danach |
| E7 | Pflaume ist Konflikt, kein Bugfix |

Pflichtseiten bleiben vor jeder sichtbaren UI-Welle.

## 1–10 und Anhänge

Der vollständige ausformulierte Text (Befunde, Stufe 1, Trace-Vertrag, Screens, Rückfall, Kandinsky Anhang A mit Punkt/Linie/Fläche, Messprotokoll) liegt kanonisch in der Artifact-Kopie:

`artifacts/docs/design/avenyth-redesign-concept.md`

GitHub-Zwilling hier im Branch wird in einem Folge-Commit 1:1 nachgezogen, falls dieser Platzhalter zu kurz ist. Inhaltlich verbindlich für das Review ist die Artifact-Datei plus die übrigen Dateien dieses Branches (`preview.html`, `adr-016-design-tokens-entwurf.md`, `tools/contrast_check.py`).

### Kandinsky (Stufe 2, Skizze)

Quellen: *Über das Geistige in der Kunst* (1911/12); *Punkt und Linie zu Fläche* (1926, Bauhausbuch 9).

- Punkt = kleinste Setzung, Ruhe, Ort.
- Linie = Spur des bewegten Punktes (eine Kraft = Gerade).
- Fläche = Grundfläche mit Spannung Zentrum/Rand.

Nehmen: Grammatik. Nicht nehmen: geistige Notwendigkeit als Produktstimme, Synästhesie, Kreis-Dreieck-Quadrat, Heilfarbe.

Ultramarin statt Gold bricht Brand §3.2 — deshalb nur Skizze.

### Trace-Allowlist

Graph: `segment_reduce`, `sum`, `reduce`. Sonst Liste. Endwert immer `metric.display_value`.

### Fiktives Beispiel

12.06.1988 von Hand: 12→3, 6, 1988→26→8, Summe 17, Reduktion 8. Engine nicht gelaufen. Keine Golden-Fixture.
