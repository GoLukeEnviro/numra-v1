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

Die Zugriffsprüfung ist unverändert die des Lesepfads (Bericht: Besitzer; Analyse: aktives Workspace-Mitglied). Das Feld verrät nichts, was der Text nicht ohnehin zeigt; Fremde und Admins erhalten wie bisher 404. Eine ältere Analyse bleibt nach einem Consent-Entzug als historischer Snapshot lesbar (bestehende Regel) und trägt dann ihre Kennzeichnung weiter; **Vorschau und Neuerzeugung** verlangen dagegen den aktuellen Consent (Abschnitt 5).

## 3. Anzeige (Web)

Betroffene Inhalte zeigen oberhalb des Textes den Hinweis „Dieser Inhalt enthält technische Platzhalter“; im Bericht trägt zusätzlich jeder betroffene Abschnitt die Marke „Enthält Platzhalter“. Der Text bleibt sichtbar und unverändert.

## 4. Betriebsbefehl (nur Lesen)

```
uv run python -m numra_api.cli content-flags scan [--list-ids]
```

Gibt je Art (`report`, `report_section`, `relationship_analysis`) nur `checked=` und `flagged=` aus; mit `--list-ids` zusätzlich die UUIDs der betroffenen Zeilen, damit die Besitzer informiert werden können. Der Befehl schreibt nichts, hat kein `--apply` und startet keine Neuerzeugung (Test `test_cli_offers_no_apply_and_no_regeneration`).

## 5. Neuerzeugung (verknüpfte neue Version)

| Ressource | Endpunkt |
|---|---|
| Bericht | `GET /v1/reports/{id}/regenerate-preview`, `POST /v1/reports/{id}/regenerate` |
| Beziehungsanalyse | `GET /v1/workspaces/{ws}/relationship-analysis/{id}/regenerate-preview`, `POST …/{id}/regenerate` |

Grundsätze:

* **Ausdrückliche Aktion, kein Massenlauf.** Es gibt keinen Batch-Endpunkt und keinen CLI-Befehl, der neu erzeugt. Die Vorschau startet nichts; sie nennt den LLM-Aufruf, die Verbrauchseinheit (1 Einheit des Features `report` bzw. `analysis`), den Stand des Limits und dass das Original erhalten bleibt. Die Web-Schaltfläche „Neu erzeugen“ öffnet zuerst diese Vorschau; gestartet wird erst mit „Jetzt neu erzeugen“.
* **Original unverändert.** Die neue Version ist eine eigene Zeile mit `regenerated_from_id` auf das Original (Migration `f8d3b6a1c4e9`, siehe unten). Das Original wird weder überschrieben noch gelöscht und bleibt abrufbar und gekennzeichnet.
* **Nur für tatsächlich betroffene Inhalte.** Ist `content_flag = none`, antwortet der Start mit 409 `CONTENT_NOT_FLAGGED`.
* **Derselbe Job-Pfad wie eine Neuerzeugung:** Beta-Gate (`require_beta_access`), Quote (`usage_quota.reserve`; Fehlschlag gibt die Einheit zurück), Worker, Speicher-Gate (#315). Ein defektes Ergebnis wird nie `COMPLETE`; die neue Version endet dann `FAILED`, das Original bleibt, und die Neuerzeugung kann erneut angestoßen werden.
* **Doppelklick = eine Version.** Die Zeile des Originals wird für die Dauer der Prüfung gesperrt; es gibt höchstens eine lebende (`PENDING`/`COMPLETE`) Neuerzeugung je Original (zusätzlich partieller Unique-Index). Weitere Klicks, auch mit anderem Idempotency-Key, liefern die bestehende Version (200) statt einer zweiten, ohne zweite Einheit und ohne zweiten LLM-Aufruf. Ein Idempotency-Key, der zu einer anderen Anfrage gehört, ergibt 409 `IDEMPOTENCY_KEY_CONFLICT`.
* **Zugriff:** Bericht nur für den Besitzer (Fremde und Admins: 404, nicht angemeldet: 401/403). Analyse nur für aktive Workspace-Mitglieder (Nicht-Mitglied: 404), bei aufgelöstem Workspace 409, und nur mit **aktuellem** beidseitigem Consent `RELATIONSHIP_INSIGHTS` (sonst 403 `CONSENT_NOT_GRANTED` – Vorschau wie Start). Admins erhalten keinen Zugriff auf fremde Inhalte. Die Analyse wird für den Workspace wie eine neue Analyse erzeugt (aktuelle Berechnungen und Beziehungsart).

**Migration** `f8d3b6a1c4e9` (Kopf auf `e5b7d1a9c3f2`, genau ein Head): zwei nullbare Spalten `regenerated_from_id` (`reports`, `relationship_analyses`, FK `ON DELETE SET NULL`) und zwei partielle Unique-Indizes. Rein additiv, keine Datenänderung; der alte Code liest die Spalten nicht, ein Rollback des Codes lässt sie ungenutzt liegen.

## 6. Ablauf für die drei betroffenen Produktionsinhalte

Grundlage ist der Befund vom 2026-10-09 (nur Zahlen): **2 von 6** Berichten mit Inhalt (13 von 84 Abschnitten) und **1 von 1** Beziehungsanalyse sind betroffen; Schatten-Dynamiken und Chat sind leer. Das sind drei Inhalte, drei Besitzer-Entscheidungen, drei LLM-Läufe.

1. **Deploy** in der üblichen Reihenfolge (Migration vor Code, additiv). PR 1 allein braucht keine Migration; es ist kein Backfill und kein Datenbefehl nötig.
2. **Zählen (Betreiber, nur Lesen):** `content-flags scan` auf Produktion; Soll: `report … flagged=2`, `report_section … flagged=13`, `relationship_analysis … flagged=1`. Weicht die Zahl ab, ist der Bestand seit dem Befund gewachsen oder die Messung zu prüfen, nicht zu „korrigieren“.
3. **Besitzer informieren (Betreiber):** mit `--list-ids` die Besitzer zu den drei Zeilen ermitteln und sie über den üblichen Kanal bitten, den betroffenen Inhalt zu öffnen. Dort steht der Hinweis „Dieser Inhalt enthält technische Platzhalter“ samt „Neu erzeugen“.
4. **Auslösen (Besitzer, nicht der Betreiber):** Bericht – der jeweilige Besitzer; Beziehungsanalyse – eines der beiden Mitglieder, sofern beide den Consent `RELATIONSHIP_INSIGHTS` aktuell erteilt haben (sonst zuerst Consent klären). Voraussetzung: Beta-Freigabe und freie Quote (Vorschau zeigt beides).
5. **Prüfen:** neue Version `COMPLETE` und `content_flag = none`; das Original bleibt gekennzeichnet und abrufbar. Der Betreiber sieht nur Zähler (`scan`), keine Inhalte.
6. **Nicht tun:** keine Neuerzeugung durch Administratoren oder per Skript, kein Löschen/Überschreiben des Originals, keine Massenaktion „für alle“.

**Empfehlung:** Neuerzeugung bleibt eine Entscheidung der Besitzer; der Betreiber liefert Zahlen und Hinweis, nicht den Auslöser. Der Hinweis im Produkt ist für den Normalbetrieb ausreichend; eine Ansprache ist nur für diese drei Inhalte sinnvoll.

## 7. Grenzen

* Schatten-Dynamiken und Copilot-Antworten tragen kein `content_flag` und haben keine Neuerzeugung (aktuell keine betroffenen Zeilen).
* Das Flag hängt am Detektor: Ein Token in einer Form, die er nicht kennt (`docs/engineering/template-token-grammar.md`), bleibt unmarkiert.
* Die Prüfung läuft synchron beim Lesen eines einzelnen Ergebnisses (ca. 20 ms für 64 000 Zeichen); Listen zeigen sie nicht.
* `content-flags scan` wurde nur gegen Testdatenbanken ausgeführt; gegen Produktion läuft er erst nach dem Deploy.
