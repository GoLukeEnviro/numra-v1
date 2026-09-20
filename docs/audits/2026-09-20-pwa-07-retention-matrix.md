# PWA-07 — Retention- und Cascade-Matrix der Kontolöschung

Stand 2026-09-20. Dieses Dokument ist die **dokumentierte Matrix**, die PWA-07 verlangt
(„the documented retention/cascade matrix for PII and pseudonymous identifiers"). Sie
ist nicht aus dem Code abgeschrieben, sondern **empirisch erhoben**: beide synthetischen
Konten wurden über das Produkt angelegt, das eine gelöscht und danach jede Tabelle mit
ForeignKey auf `users.id` gezählt.

Erzwingender Test: `apps/api/tests/integration/test_account_deletion_cascade_matrix.py`
(5 Tests). Eine neue Tabelle mit FK auf `users.id`, die in keiner Kategorie steht, lässt
`test_every_user_referencing_table_is_covered_by_the_matrix` fehlschlagen — die Matrix
kann also nicht still veralten.

## Die Regel

Die Löschung ist ein **Soft-Delete mit PII-Tilgung**, kein `DELETE FROM users`. Die
`users`-Zeile überlebt als Tombstone, damit die FKs geteilter Relationship-Artefakte
gültig bleiben und der Partner seine gemeinsame Historie behält
(`repositories/account.py`, Modul-Docstring). Daraus folgt die zentrale Konsequenz:

> Weil die Elternzeile überlebt, **feuert `ondelete=CASCADE` nie**. Jede rein private
> Kindtabelle muss deshalb explizit gelöscht werden.

Maßgeblich ist ADR-013 (`docs/adr/013-v2-workspace-dissolution.md`): privater Inhalt
verschwindet, geteilte Artefakte bleiben lesbar mit dem gelöschten Nutzer
pseudonymisiert, und es darf keine verwaiste PII und keine fremden privaten Daten
zurückbleiben.

## Matrix

### 1 — Entfernt (privater Inhalt, kein Inhalt = weg)

| Tabelle | Spalte | Nachweis |
|---|---|---|
| `people` | `user_id` | 0 nach Löschung |
| `private_reflections` | `user_id` | 0 |
| `private_notes` | `user_id` | 0 |
| `personal_tasks` | `user_id` | 0 |
| `pattern_analyses` | `user_id` | 0 |
| `relationships` | `user_id` | 0 |
| `chat_threads` | `owner_user_id` | 0 |
| `reports` | `user_id` | 0 |
| `report_jobs` | `user_id` | 0 |
| `exports` | `user_id` | 0 |
| `sessions` | `user_id` | 0 |
| `email_verification_tokens` | `user_id` | 0 |
| `password_reset_tokens` | `user_id` | 0 |
| `life_tracking_entries` | `user_id` | 0 |
| `checkin_responses` | `user_id` | 0 |
| `thread_context_snapshots` | `requester_user_id` | 0 |

Nicht durch eigene `DELETE`-Aufrufe, sondern über die Kaskade der Elternzeile:
`report_sections`/`llm_generations` (unter `reports`/`report_jobs`),
`name_identities`/`calculations` (unter `people`).

### 2 — Erhalten (geteilte Historie und Audit-Spur)

| Tabelle | Spalte | Zustand nach Löschung |
|---|---|---|
| `user_connections` | `user_a_id` | Zeile bleibt, `status=DISSOLVED` |
| `workspace_members` | `user_id` | Zeile bleibt, `status=REMOVED` |
| `workspace_tasks` | `proposer_user_id` | bleibt |
| `relationship_roadmaps` | `proposer_user_id` | bleibt |
| `shared_reflections` | `author_user_id` | bleibt |
| `consent_grants` | `grantor_user_id` | bleibt, `revoked_at` gesetzt |
| `consent_events` | `actor_user_id` | bleibt (Audit-Trail) |
| `connection_invitations` | `inviter_user_id` | bleibt |
| `task_acceptances` | `actor_user_id` | bleibt |
| `analysis_jobs` | `requested_by_user_id` | bleibt — ausdrücklich als erhaltener geteilter FK dokumentiert |
| `entitlement_assignments` | `user_id` | bleibt — trägt keine PII |
| `checkin_idempotency` | `user_id` | bleibt — führt laut Modell-Docstring keinen privaten Response-Cache |

Die letzten drei sind die nicht offensichtlichen Fälle und der Grund, warum diese Matrix
überhaupt nötig war — siehe „Was diese Arbeit gefunden hat".

### 3 — Vom Fixture nicht befüllt, aber klassifiziert

`chat_messages` (kein Verlauf im Seed) und `admin_audit_events` (Admin-Pfad nicht
ausgelöst). Sie stehen bewusst in der Klassifikation, damit die Coverage-Prüfung
aussagekräftig bleibt; über sie wird keine Mengenaussage gemacht. Für beide gilt
weiterhin die globale FK-Integrität.

## Die systematische Hälfte

Mengenaussagen pro Tabelle fangen eine vergessene Tabelle nur, wenn man sie vorher
kennt. Deshalb prüft `test_no_dangling_foreign_keys_anywhere_in_the_schema`
**jeden** Single-Column-ForeignKey des gesamten Schemas gegen den Elternbestand
(> 30 geprüft): Ein Verweis, der nach der Löschung ins Leere zeigt, lässt den Test
scheitern — unabhängig davon, ob jemand die Tabelle in die Matrix eingetragen hat.

## Was diese Arbeit gefunden hat

Die Matrix war beim ersten Schreiben in drei Punkten falsch, und der Test hat jeden
davon aufgedeckt:

1. **`entitlement_assignments` und `checkin_idempotency` als „privat" klassifiziert.**
   Ich habe daraufhin einen Löschpfad ergänzt — und damit eine dokumentierte
   Entscheidung widerlegt. `test_delete_all.py` hält ausdrücklich fest: „trägt keine
   PII … PR-V2-10 löscht bewusst nur inhaltstragende Privatdaten". Der Produkt-Eingriff
   wurde **vollständig zurückgenommen**; beide Tabellen stehen jetzt unter „erhalten".
   Lehre: eine beobachtete Abweichung ist erst dann ein Defekt, wenn sie der
   dokumentierten Absicht widerspricht.
2. **`analysis_jobs` als „privat" klassifiziert.** Der Modul-Docstring in
   `repositories/account.py` nennt `AnalysisJob` explizit als bewusst erhaltenen
   geteilten FK. Ebenfalls korrigiert.
3. **Vakuose Assertions.** Der Seed befüllte die meisten Privat-Tabellen gar nicht —
   `0 == 0` wäre auch dann grün gewesen, wenn der Löschpfad die Tabelle komplett
   ignoriert. Eine Mutationsprobe gegen `delete_private_content` blieb grün und hat das
   bewiesen. Der Seed befüllt jetzt **jede** Tabelle aus Kategorie 1, und der Test
   verlangt vor der Löschung `>= 1` pro Tabelle — eine ungefüllte Tabelle lässt ihn
   scheitern statt still nichts zu prüfen.

## Offene Dokumentationslücke

Die Begründung „PR-V2-10 löscht bewusst nur inhaltstragende Privatdaten" verweist auf
„Blueprint §2.3". Ein solches Dokument liegt **nicht im Repository** — es ist die
einzige repo-interne Quelle für den Löschumfang und steht als Kommentar in einer
Testdatei. Wer den Umfang künftig ändern will, findet die Begründung nur dort.

## Reproduktion

```bash
export PATH="/home/hermes/.hermes/bin:/home/hermes/.local/bin:$PATH"
docker exec numra-test-pg psql -U numra -d numra_test \
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
TEST_DATABASE_URL="postgresql+asyncpg://numra:numra_dev_password@127.0.0.1:5432/numra_test" \
TEST_PDF_URL="http://127.0.0.1:4300" TEST_PDF_TOKEN="test-token" \
uv run pytest apps/api/tests/integration/test_account_deletion_cascade_matrix.py -q
```

Die Matrix wurde zusätzlich per Einzelabfrage über alle FK-Spalten erhoben
(`/tmp/numra-pw/retention_matrix.py`, nicht Teil des Repos: Diagnosewerkzeug).

## Nicht abgedeckt

Der **Datenexport** des Kontos. Der Auftrag für PWA-07 verlangt „export one synthetic
account, inspect the documented schema" — der Export-Pfad im Produkt ist jedoch
ausschließlich ein PDF-Render eines Reports; `ExportType.JSON` ist nicht erreichbar.
Das ist als Issue erfasst und blockiert den Exit-Gate-Teil „Export", nicht die
Lösch- und Cascade-Nachweise dieses Dokuments.
