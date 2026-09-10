# PR-WEB-06a — Backend-/Migrationsnachweise

Stand: Implementierung und finale gezielte lokale Prüfungen abgeschlossen; PR #53 in CI.
Basis: `8808c033a36c43fb394f8ed3d867f6fa3a7685ce` (PR #52).
Branch: `codex/pr-web-06a`. Kein Produktionsdeployment, keine Flag-Aktivierung.

## Umsetzung und Contract

A1–A10: explizite Runden, unveränderliche Fragen-Snapshots, Herkunftskennzeichnung,
vollständige und skalenvalidierte Abgabe, persistierte Idempotenz für Start/Submit,
automatische Template-Versionen, historische Reads, Config-/Typwechsel-Sperre,
INTIMATE-Klassifikation, Workspace-Transaktionsschutz, Current-Route, OpenAPI und
TypeScript-Client. Vollständige Details: `specs/v2/checkin-spec.md` (WEB-06a).

Kompatibilitätsbruch für alte Submit-Aufrufer: erst Runde eröffnen; dann `round_id`
und einen pro Versuch stabilen `Idempotency-Key` senden. Alle Antworten sind Pflicht.
Client-Aufrufer behalten denselben Key bei Netzwerk-Retry, erzeugen einen neuen Key
für einen neuen fachlichen Versuch. Replay gibt die identische Runden-ID mit aktuell
autorisiertem Zustand zurück; es ist kein eingefrorener HTTP-Response-Cache.
Neue Pflichtheader sind in CORS erlaubt. 06b-Oberflächen bleiben unimplementiert.

## Migration e6a1b2c3d4e5

Vorheriger Head: `d4e5f6a7b8c9`.

- Additiv: `checkin_round_dimensions`, `checkin_idempotency`, `snapshot_origin`,
  `dimension_class`. Änderung des Dimensions-Unique-Constraints auf
  `(workspace_id, template_version, semantic_key)`; partieller Unique-Index für
  höchstens eine aktive Template-Version (Existenz durch Service). Bekannter Key sexual_connection → INTIMATE.
- ANALYZED-Bestandsantworten und Analyse-JSON bleiben unverändert. Keine erfundenen
  Fragebeschriftungen: Snapshot fehlt ehrlich (`LEGACY_MISSING`).
- AWAITING-Preflight prüft aktives Template, nichtleere Dimensionsmenge, zwei aktive
  Mitglieder, höchstens einen bisherigen Submitter, keine bestehende Analyse,
  exakte vollständige Antwortmenge, passende Keys/Referenzen und Skalenwerte.
- Kompatible offene Bestände erhalten einen Snapshot der Migrationskonfiguration
  mit `MIGRATION_CURRENT`. Geänderte damalige Beschriftungen sind nicht rekonstruierbar;
  dieses Flag behauptet ausdrücklich keinen ursprünglichen Rundenstart-Snapshot.
- Unvollständige/inkonsistente Bestände: `CHECKIN_MIGRATION_INCOMPATIBLE`, nur Anzahl
  betroffener Runden/Template-Konflikte. Keine Rohwerte oder privaten Texte im Fehler.
  PostgreSQL-Transaktion rollt DDL, Backfill und Alembic-Version vollständig zurück.
- DB-Trigger verhindern Dimensions-Identitätsänderungen, Änderungen an genutzten
  Versionszeilen und direkte Snapshot-UPDATEs/DELETEs. Parent-Cascade bleibt möglich.
  Aufgeschobene NO-ACTION-FKs schützen historische Antwort-/Snapshot-Referenzen,
  auch wenn vor der ersten Antwort eine Dimension gelöscht werden soll. Prüfung am
  Transaktionsende erhält zugleich die vollständige Workspace-Cascade.
- Downgrade sperrt Writer vor der Nutzungsprüfung. Sobald Snapshots, Idempotenz,
  neuere Versionen oder neue Custom-Klassifikationen bestehen, Abbruch mit
  `CHECKIN_DOWNGRADE_UNSAFE`. Kein destruktives Zurückkopieren oder Zusammenlegen.

### Verlustfreies Verfahren bei inkompatiblen Beständen

1. Migration nicht erneut blind ausführen; Originaldatenbank und Diagnose erhalten.
   Alten Anwendungsstand beibehalten. Für eine spätere echte Migration ist ein
   Wartungsfenster ohne alte Writer und ein verifiziertes Backup nötig.
2. Ausschließlich auf einer isolierten Backup-Kopie betroffene Runden mit ihren
   Originalantworten, IDs, Template-Bezügen und Analysezuständen inventarisieren.
   Personen-/Antwortdaten bleiben in dieser geschützten Kopie, nicht in Logs/PRs.
3. Keine Antwort nachtragen, löschen, umdeuten oder aktuelle Texte als ursprünglich
   ausgeben. Insbesondere eine Teilabgabe darf nicht als vollständige gelten.
4. Konkreter verlustfreier Folgeentwurf: inkonsistente Altrunden in einem separat
   geplanten Migrationsschritt als historisch unvollständig/read-only archivieren,
   Originalantworten und References unverändert behalten und eine neue explizite
   Runde mit neuem Snapshot zulassen. Dafür braucht es einen ausdrücklich festgelegten
   Legacy-Archivstatus und Read-Contract; WEB-06a führt diesen zusätzlichen Lifecycle
   nicht still ein. Keine Analyse für unvollständige Altdaten erfinden.
5. Erst nach geprüfter Folgemigration und Restore-Probe erneut migrieren. Nach Nutzung
   des neuen Schemas ist Rollback nur über ein geprüftes Vorher-Backup oder eine neue
   verlustfreie Forward-Migration zulässig. Ein Backup-Restore muss zwischenzeitliche
   neue Daten gesondert sichern; er ist keine automatisch verlustfreie Rücknahme.

Dieser Auftrag enthält keine Freigabe für einen Produktionsdatenbank-Eingriff.
Die unten genannten inkonsistenten Daten sind ausschließlich synthetische Testfälle.

## Reproduzierbare lokale Prüfung

Windows/PowerShell, uv/pnpm aus vorhandenem Projektwerkzeugbestand, Postgres 16.
Keine neuen Abhängigkeiten. Eigener Container `numra-web06a-postgres`, Loopback-Port
5546; eigene PDF-Testinstanz auf 4346. Bestehende Container/Volumes unverändert.

```powershell
uv sync --all-packages --all-groups
pnpm install --frozen-lockfile
docker run -d --name numra-web06a-postgres `
  -e POSTGRES_USER=numra -e POSTGRES_PASSWORD=web06a_test_only `
  -e POSTGRES_DB=numra_web06a -p 127.0.0.1:5546:5432 postgres:16-alpine
$env:TEST_DATABASE_URL='postgresql+asyncpg://numra:web06a_test_only@127.0.0.1:5546/numra_web06a'
# In einem separaten Terminal, nur synthetischer lokaler Testtoken:
$env:PORT='4346'; $env:PDF_INTERNAL_TOKEN='web06a-pdf-test'
pnpm --filter @numra/pdf start
# Im Testterminal:
$env:TEST_PDF_URL='http://127.0.0.1:4346'; $env:TEST_PDF_TOKEN='web06a-pdf-test'
uv run pytest packages apps/api/tests -q
uv run pytest apps/api/tests/integration/test_checkin_migration.py -q
uv run ruff check .
uv run mypy apps/api/src packages/engine-numerology/src packages/engine-interpretation/src packages/engine-relationship-interpretation/src packages/engine-astrology/src
uv run python scripts/export_openapi.py --check
pnpm --filter @numra/schema generate
git diff --exit-code -- packages/schema/src/generated
pnpm --filter @numra/web lint
pnpm --filter @numra/web exec tsc --noEmit
pnpm --filter @numra/web run test
pnpm --filter @numra/web build
```

Migrationssuite erstellt pro Fall eine eigene `web06a_migration_<UUID>`-Datenbank
und entfernt ausschließlich diese in der Fixture-Nachbereitung. Sie verwendet echte
Alembic-Subprozesse statt `metadata.create_all`. Die übrigen Integrationstests nutzen
die vorhandene create_all-Fixture; Trigger werden deshalb explizit auf migrierten
Schemas geprüft. DB-Tests mit create_all niemals parallel gegen dieselbe DB ausführen.

## Review und Fehlerdiagnosen

Unabhängiger Subagent-Review (read-only), getrennt vom implementierenden Agenten:
Vorabreview der Lock-/Migrationsarchitektur, Zwischenreview, Abschlussreview und
gezielter Nachreview. Kein fremder Review wird als selbst ausgeführter Test ausgegeben.

Behobene Befunde:

- frischer Workspace + Default-Key konnte beim Lazy-Seed eine UniqueViolation erzeugen;
- Downgrade-Nutzungsprüfung benötigte dieselbe Writer-Sperre bereits vor dem SELECT;
- Current-Vorauswahl vor Lock konnte alten Status mit neuer Analyse kombinieren;
- unbekannte Payloadfelder/Start-Bodies wurden zuvor still ignoriert;
- Dimensionslöschung vor erster Antwort musste ebenso geschützt werden;
- verschärfte Migrationstests bewiesen, dass sofortige RESTRICT-FKs die vollständige
  Workspace-Cascade blockierten; ersetzt durch aufgeschobene FK-Prüfung.

Rot→Grün: `/current` lieferte vor Fix 422 (als UUID interpretiert), danach 200/null.
Erster Fixture-Versuch mit abgelehnter Login-Maildomain war kein Regressionnachweis;
Fixture wurde vor dem eigentlichen Rot→Grün-Lauf korrigiert. Ein lokaler Web-Testaufruf
scheiterte am PowerShell/pnpm-Argumentparser (`--run`); korrekt ist das bestehende
Script `pnpm --filter @numra/web run test` (= `vitest run`). Keine Tests abgeschwächt.

Paralleltests verifizieren vor Freigabe des ersten Commits zwei unterschiedliche
Postgres-PIDs und den tatsächlichen Blocker via `pg_blocking_pids`, mit Timeouts und
gezielter Task-Nachbereitung. Kein bloßes gather als Konkurrenzbeweis. Enthalten sind
Start/Start, Start/Config, Start/Typ, Submit/Submit (20 Runden), gleicher/anderer Key,
veränderter Payload, Config/Config, Mutationen gegen Dissolve in beiden Reihenfolgen,
Current gegen zweiten Submit und Mitgliedschaftsentzug während Lock-Wartezeit.

## Finale Ergebnisse / CI

- Finaler gezielter Backend-Lauf: **86 passed**, 324,66 s. Dateien: checkins,
  checkin_rounds, checkin_concurrency, dissolution, account_deletion,
  relationship_workspaces. Enthält alle nach dem Review ergänzten Fälle.
- Finale echte Alembic-Migrationssuite: **10 passed**, 121,57 s; einschließlich
  Dimensions-/Snapshot-Löschschutz, Parent-Cascade und atomarem Rollback.
- Breiter Vorab-Lauf `pytest packages apps/api/tests -q`: **740 passed, 1 failed**,
  1162,50 s. Einzige Ursache war die inzwischen korrigierte Sortierungsannahme im
  Retire-Test. Der finale gezielte Lauf bestätigt diesen Fix; den vollständigen
  finalen Stand prüft zusätzlich der Required-CI-Job `unit-and-property-tests`.
- Python-Lint und strikter Mypy: grün (202 Quelldateien).
- Web: ESLint, Typecheck, **244 Tests / 55 Dateien** und Next.js Build grün.
- OpenAPI und generierter TypeScript-Client aktualisiert; finale Driftprüfung vor Push.
- Keine weitere offene konkrete Review-Feststellung; Laufzeitbefunde behoben.

Noch ausstehend: PR-Commit/Required Checks, Merge-SHA und getrennte Post-Merge-main-CI.
Diese werden nach Abschluss ergänzt; kein Produktionsdeployment.


### PR-CI Versuch 1 — Encoding-Diagnose

Run `34527084231`, Commit `d97e399`: `lint-python` scheiterte in
`ruff format --check .`. Drei bearbeitete Markdown-Dateien enthielten durch die
Windows-Standardkodierung beim Python-Schreiben einzelne CP1252-Fragmente in UTF-8.
Der lokale Reproduktionsbefehl bestätigte exakt diese Dateien. Explizites UTF-8
und normalisierte LF-Zeilenenden beheben die Ursache. Der erste Encoding-Fix wurde
zusätzlich auf LF korrigiert, nachdem `git diff --check` doppelte CR-Zeichen zeigte.
Format-Check, Lint und Diff-Check werden vor dem finalen Push vollständig wiederholt.
Kein Re-Run desselben Commits und keine Abschwächung der CI.


### Vollsuite und zusätzlicher Compose-Startup-Befund

Run [34527452954](https://github.com/GoLukeEnviro/numra-v1/actions/runs/34527452954)
auf `e8d12c8`: alle zwölf Checks erfolgreich; finale Python-Vollsuite **747 passed**,
486,52 s. Separates Engine-Coverage-Gate: **110 passed, 100 %**.

Der erste Run `34527084231` hatte neben Encoding einen zweiten Fehler: Compose-
Browser-Journey **1 passed**, anschließend strikter Log-Audit rot. PostgreSQL meldete
um 20:36:11.794 UTC `FATAL: the database system is starting up`, 173 ms vor seiner
Ready-Meldung. Ein pg_isready-Startup-Paket war während Startup angekommen. Dies ist
ein anderer Mechanismus als der bereits behobene Commit-vor-Response-Fehler.

Die Compose-Härtung prüft vor einer Verbindung den finalen Postmaster (PID 1) und
Statuszeile 8 (`ready`) der PID-Datei, anschließend TCP mit BusyBox `nc -z -w 1` ohne
Nutzdaten. PostgreSQL behandelt EOF vor dem ersten Startup-Byte ausdrücklich ohne
Fehlerlog; ein libpq-Startup-Paket könnte bei zwischenzeitlichem Shutdown dagegen
weiterhin FATAL auslösen. Quellen: [PostgreSQL 16 postmaster.c](https://raw.githubusercontent.com/postgres/postgres/REL_16_STABLE/src/backend/postmaster/postmaster.c),
[PID-Dateiformat](https://raw.githubusercontent.com/postgres/postgres/REL_16_STABLE/src/include/utils/pidfile.h).
Der Log-Audit bleibt unverändert streng. Keine längere pauschale Wartezeit.

Reproduzierbar: `uv run python scripts/verify_postgres_startup.py` — fünf frische
Postgres-16-Container plus je ein Neustart desselben initialisierten anonymen Volumes,
Health-Probes alle 100 ms: **10/10 gesund, SQL erreichbar, stdout UND stderr ohne
Traceback/Unhandled/FATAL/panic**. Geschlossener TCP-Port muss jeweils scheitern.
Container und ausschließlich ihre eigenen anonymen Volumes werden entfernt. Die
PID-1-Annahme gilt für die vorhandene Compose-Konfiguration ohne init/Wrapper;
bei späterer Änderung dieser Topologie muss der Healthcheck angepasst werden.
Unabhängiger Nachreview des Startup-Mechanismus erfolgt. Die Härtung erhält einen
neuen Commit und einen vollständigen neuen CI-Lauf vor Merge.
