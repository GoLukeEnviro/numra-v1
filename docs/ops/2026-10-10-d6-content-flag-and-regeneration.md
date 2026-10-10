# D6: Gespeicherte Inhalte mit Template-Tokens – Kennzeichnung und Neuerzeugung

**Stand:** 2026-10-10 · Grundlage: `docs/ops/2026-10-09-stored-token-audit.md` (Befund, schreibfrei)

## 1. Entscheidung

| Frage | Entscheidung | Begründung |
|---|---|---|
| Welche Inhalte gelten als betroffen? | Nur solche, bei denen der strenge Detektor (`find_unresolved_token_in_payload`, dasselbe Prüfwerk wie das Speicher-Gate #315) einen Treffer meldet. | Ein alter Erstellungszeitpunkt oder eine alte Prompt-Version allein markiert nichts (Test `test_age_alone_does_not_flag`). |
| Wann wird geprüft? | **Beim Lesen eines einzelnen Ergebnisses**, serverseitig, ohne Schreibzugriff, ohne Cache. | Kein Schema, kein Backfill, kein Zustand, der vom Detektor oder von den Daten abweichen kann. Kosten: ca. 20 ms für einen Bericht mit 64 000 Zeichen (gemessen), begrenzt durch die Detektor-Limits (30 000 Zeichen je Text, 300 000 je Ergebnis; darüber wird markiert, das Gate würde ebenso ablehnen). Listen berechnen das Feld bewusst nicht (50 Prüfungen je Anfrage würden die Event-Loop blockieren; Karten liefern keinen Inhalt). |
| Warum kein persistiertes Flag mit Backfill? | Verworfen. | Ein gespeichertes Flag müsste mit jeder Detektor-Härtung nachgezogen werden, braucht einen schreibenden Befehl auf Produktionsdaten und kann der Wahrheit widersprechen. Das Lesen kostet bei der tatsächlichen Datenmenge (6 Berichte, 1 Analyse) nichts. |
| Was passiert mit dem Text? | Er wird **unverändert** ausgegeben; die Prüfung läuft nur über eine Prüfansicht (`canonical_for_check`). Es wird nichts versteckt, überschrieben oder gelöscht. | Originale bleiben erhalten (Revisionssicherheit). |

## 2. API

| Ressource | Neue Felder (nur lesend) |
|---|---|
| `GET /v1/reports/{id}` | `content_flag` (`none` \| `unresolved_template_tokens`), `flagged_section_ids` (Abschnitte, die selbst einen Treffer haben) |
| `GET /v1/workspaces/{ws}/relationship-analysis[/{id}]` | `content_flag` |

Modus je Pipeline: Bericht locker (`strict_braces=False`), Beziehungsanalyse streng (`strict_braces=True`). Nicht `COMPLETE` oder ohne Inhalt: `none`.

Die Zugriffsprüfung ist unverändert die des Lesepfads (Bericht: Besitzer; Analyse: aktives Workspace-Mitglied). Das Feld verrät nichts, was der Text nicht ohnehin zeigt; Fremde und Admins erhalten wie bisher 404. Eine ältere Analyse bleibt nach einem Consent-Entzug als historischer Snapshot lesbar (bestehende Regel) und trägt dann ihre Kennzeichnung weiter; **Vorschau und Neuerzeugung** verlangen dagegen den aktuellen Consent (Folge-PR).

## 3. Anzeige (Web)

Betroffene Inhalte zeigen oberhalb des Textes den Hinweis „Dieser Inhalt enthält technische Platzhalter“; im Bericht trägt zusätzlich jeder betroffene Abschnitt die Marke „Enthält Platzhalter“. Der Text bleibt sichtbar und unverändert.

## 4. Betriebsbefehl (nur Lesen)

```
uv run python -m numra_api.cli content-flags scan [--list-ids]
```

Gibt je Art (`report`, `report_section`, `relationship_analysis`) nur `checked=` und `flagged=` aus; mit `--list-ids` zusätzlich die UUIDs der betroffenen Zeilen, damit die Besitzer informiert werden können. Der Befehl schreibt nichts, hat kein `--apply` und startet keine Neuerzeugung (Test `test_cli_offers_no_apply_and_no_regeneration`).
