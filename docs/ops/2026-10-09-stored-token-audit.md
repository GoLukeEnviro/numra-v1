# Befund: Template-Tokens in gespeicherten Produktionsinhalten

**Stand:** 2026-10-09 · **Umfang:** nur Lesen (`SELECT`), keine Änderung an Daten, Containern oder Deploy
**Werkzeug:** `scripts/ops/audit_stored_tokens.py` (liest JSON-Zeilen von stdin, gibt ausschließlich Zähler aus – nie einen Text, eine ID oder einen Personenbezug)
**Detektor:** gehärtete Fassung dieses PR sowie zum Vergleich der Stand `main` b29bffd (`rendering_guard.py` ohne die Härtung)

## 1. Methode

Die Inhalte flossen per Pipe vom `psql` im Container `numra-prod-postgres-1` direkt in das Skript auf dem Host. Auf dem Terminal erschien nur die Zähl-Ausgabe. Geprüft wurde jedes Dokument im Modus der Pipeline, die es erzeugt hat (Analyse und Schatten streng, Report und Chat locker). Quellen:

| Quelle | Spalte | Filter |
|---|---|---|
| `reports` | `content_json` | nicht `NULL` |
| `report_sections` | `content_json` | alle (Join auf `reports` nur für die Prompt-Version) |
| `relationship_analyses` | `result_json` | nicht `NULL` |
| `shadow_dynamics_analyses` | `result_json` | nicht `NULL` |
| `chat_messages` | `content` | `role = 'ASSISTANT'`, nicht leer |

Zusätzlich wurde das grobe Alt-Muster `\[[a-z]:[a-z_]+\]|\{\{[^}]*\}\}` mitgezählt und mit dem Detektor verglichen.

## 2. Bestand

| Tabelle | Zeilen | davon mit Inhalt |
|---|---:|---:|
| `reports` | 18 (6 `COMPLETE`, 12 `FAILED`) | 6 (die `FAILED` haben kein `content_json`) |
| `report_sections` | 84 | 84 |
| `relationship_analyses` | 1 (`COMPLETE`) | 1 |
| `shadow_dynamics_analyses` | 0 | 0 |
| `chat_messages` | 0 | 0 |

Die bekannten Zahlen „reports 2/18, report_sections 13/84, relationship_analyses 1/1" bestätigt die Messung (SQL-Regex); der Nenner 18 enthält 12 Zeilen ohne Inhalt, **wirksam sind 2 von 6**.

## 3. Ergebnis (Detektor)

| Quelle | Dokumente | mit Treffer | Kategorie | betroffenes Feld (Zeichenketten) |
|---|---:|---:|---|---|
| `reports` | 6 | **2** | Platzhalter (`{{…}}`) | `summary` (13) |
| `report_sections` | 84 | **13** | Platzhalter | `summary` (13) |
| `relationship_analyses` | 1 | **1** | Platzhalter, Kurz-Label, einzelne Klammer | `text` (6 von 79 Zeichenketten) |
| `shadow_dynamics_analyses` | 0 | 0 | – | – |
| `chat_messages` | 0 | 0 | – | – |

Aufschlüsselung nach Prompt-Version (Bucket = `prompt_version/status`):

* Report: `numra-report-v2/COMPLETE` 5 Berichte (2 betroffen), `numra-report-v1/COMPLETE` 1 Bericht (0 betroffen). Abschnitte: v2 13 von 70, v1 0 von 14.
* Beziehungsanalyse: `numra-relationship-v2/COMPLETE`, 1 von 1.

## 4. Echte Treffer oder Prosa?

* **Alle Alt-Muster-Treffer sind echte Treffer.** `legacy_regex_documents_detector_clean = 0` in jeder Quelle, d. h. kein Dokument enthält eine Alt-Muster-Fundstelle, die der Detektor als Prosa durchlässt. Legitime Prosa mit der Form `[x:y]` oder `{{…}}` gibt es in den gespeicherten Daten nicht.
* **Die Härtung ändert den Befund nicht.** Der Stand `main` b29bffd und die gehärtete Fassung liefern identische Zählungen. Neue Kategorien (Look-alikes, Füllzeichen, Format-Felder, unbekanntes Kurz-Label in der Analyse) kommen in den vorhandenen Inhalten nicht vor.
* **Die Treffer liegen in `summary`** (Report) bzw. `text` (Analyse). Das entspricht den Defekten, die #308 im Code geschlossen hat (Zusammenfassung ohne Platzhalter-Auflösung; Kurz-Label `[a:life_path]`). Die Analyse stammt aus Prompt-Version `numra-relationship-v2`, älter als der aktuelle v4-Prompt. Ob und seit wann #308 in Produktion läuft, ist Release-Stand und nicht Teil dieser Messung.
* **Abgrenzung:** Betroffen ist nur, was einen Treffer hat. Ein alter Erstellungszeitpunkt allein macht ein Dokument nicht betroffen; die übrigen 4 Berichte und 71 Abschnitte ohne Treffer bleiben unberührt.

## 5. Grenzen der Aussage

* Gemessen wurde der Bestand am 2026-10-09; später erzeugte Inhalte sind nicht erfasst.
* Der Detektor kennt die in `docs/engineering/template-token-grammar.md` beschriebene Grammatik. Ein Token in einer anderen Form wäre auch hier unsichtbar; die bekannte Restlücke ist das unbekannte Kurz-Label ohne Unterstrich in Report und Copilot (dort bewusst Prosa). Der Bestand enthält keinen Fall.
* Zeichenketten sind einzeln geprüft. Ein Token, das sich erst über zwei Felder zusammensetzt, wäre nicht auffällig.

## 6. Folge und offene Entscheidung

Dieser PR verändert **keine** Daten. Ob die 2 Berichte (13 Abschnitte) und die 1 Beziehungsanalyse neu erzeugt, mit sichtbarem Hinweis versehen oder zurückgezogen werden, ist eine eigene Entscheidung nach der 24-h-Beobachtung; sie braucht einen Schreibzugriff und ein Backup-Gate. Die Zählung lässt sich jederzeit wiederholen:

```bash
# auf dem Host, im Repository mit synchronisierter Umgebung; die Inhalte erreichen das Terminal nie
docker exec numra-prod-postgres-1 psql -U numra -d numra -tAc "SELECT json_build_object(
  'kind','report','bucket',prompt_version||'/'||status,'payload',content_json)::text
  FROM reports WHERE content_json IS NOT NULL" \
  | uv run python scripts/ops/audit_stored_tokens.py
```

Die Kinds `report_section`, `relationship`, `shadow` und `chat` werden mit der jeweiligen Abfrage analog gespeist; das Skript zählt je `kind` im passenden Modus.
