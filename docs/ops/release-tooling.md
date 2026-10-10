# Release-Werkzeuge: Aufruf, Parameter, Grenzen

Skriptgestützte Fassung des Ablaufs aus
[release-verification.md](release-verification.md) (Abschnitt "Produktionsauslieferung").
Die Skripte ersetzen nicht die Freigabeentscheidung, sondern machen die dort beschriebenen
Prüfungen wiederholbar, abbrechend und nachweisbar.

| Datei | Zweck |
|---|---|
| `scripts/release/numra-release.sh` | Phasen `baseline`, `pre`, `prep`, `switch`, `marker`, `rollback` |
| `scripts/release/numra-drill.sh` | Restore- und Rollback-Drill in isolierter Umgebung |
| `scripts/release/drill_probe.py` | HTTP-Sonde des Drills (läuft im API-Container) |
| `scripts/release/release.env.example` | dokumentierte Beispielkonfiguration (einzige Stelle mit Host-Eigenheiten) |
| `scripts/ops_report/report.py` | gemeinsame Berichtserzeugung (Markdown + JSON) und Prüfung des Abnahmeberichts |
| `scripts/release/tests/` | Testharnesse mit Attrappen (kein Docker, kein Host-Zugriff) |

## Grundregeln

- **Ziel immer explizit:** `--target audit|prod` hat keinen Default. Die Konfigurationsdatei
  trägt `CONFIG_TARGET`; passt sie nicht zu `--target`, verweigert das Skript (Exit 2).
  Eine Konfigurationsdatei je Ziel.
- **Prod-Schutzschalter:** `prep`, `switch`, `marker`, `rollback` gegen `prod` brauchen
  `--i-am-sure-prod` und `--confirm-sha <erste 8 Zeichen der zu deployenden SHA>`
  (bei `rollback` die der `--old-sha`). Der Drill mit prod-Dump braucht `--i-am-sure-prod`.
- **Projektverzeichnis:** `PROJECT_DIR` (Standard: Verzeichnis von `COMPOSE_FILE`) wird immer als `--project-directory` übergeben, auch für die im Staging-Ordner liegende neue Compose; relative Build-Kontexte und Binds lösen sich so wie bei der Live-Compose auf (im Host-Skript `--project-directory /opt/numra`). Die Sicherung in `prep` enthält Konfig/Units (`BACKUP_FILES`) und `fingerprint.txt` (Image-IDs, alembic, Invariante).
- **Alles per Konfiguration:** Pfade, Projektname, Dienste, URLs, Env-Dateien, Image-Präfix.
  Das Skript enthält keine Host-Defaults; fehlende Pflichtwerte führen zu Exit 2.
- **Fehler brechen ab:** `set -euo pipefail`, jede Prüfung beendet den Lauf mit Exit 1 und
  einem `FAIL` im Bericht. Es gibt kein `|| true` an Prüfungen (der Test prüft das statisch).
- **Keine Secrets:** Env-Dateien werden nur als Pfad an `docker compose --env-file` gereicht,
  nie gelesen oder ausgegeben. Der Drill erzeugt Passwörter pro Lauf in 0600-Dateien und
  übergibt sie per `--env-file`, nicht als Argument. xtrace ist abgeschaltet; nicht mit
  `bash -x` starten. Berichte laufen durch `redact` (Mails, UUID-Reste, lange Tokens).
- **Konfigurationsvertrauen:** Die Konfigurationsdatei wird als Shell gelesen. Sie muss dem aufrufenden Benutzer oder root gehören und darf für Gruppe/Andere nicht schreibbar sein (Exit 2). `SUDO_CMD` gilt nur aus dieser Datei, nie aus der Umgebung. `release.log` und Berichte werden redigiert (zusätzlich Werte der in `REDACT_ENV` genannten Umgebungsvariablen).
- **Dry-Run:** `--dry-run` führt nur die lesenden Voraussetzungen aus, gibt den Plan als
  `SKIP plan:...` aus und mutiert nichts. Geschrieben wird ausschließlich `REPORT_DIR`
  (Bericht, Log).

## Aufruf

```bash
CFG=~/release-prod.env     # aus release.env.example, Rechte 0600
S=scripts/release/numra-release.sh

$S --target prod --config $CFG --phase baseline --old-sha <ALT>
$S --target prod --config $CFG --phase pre  --old-sha <ALT> --new-sha <NEU> [--dry-run]
$S --target prod --config $CFG --phase prep --old-sha <ALT> --new-sha <NEU> \
   --i-am-sure-prod --confirm-sha <NEU8>
$S --target prod --config $CFG --phase switch --old-sha <ALT> --new-sha <NEU> \
   --expect-revision <ZIEL_REV> --i-am-sure-prod --confirm-sha <NEU8>
# Abnahme (Smoke/Acceptance, siehe acceptance-tooling.md) -> JSON-Bericht
$S --target prod --config $CFG --phase marker --old-sha <ALT> --new-sha <NEU> \
   --smoke-report <abnahme.json> --i-am-sure-prod --confirm-sha <NEU8>
$S --target prod --config $CFG --phase rollback --old-sha <ALT> --i-am-sure-prod --confirm-sha <ALT8>
```

Exit-Codes: `0` ok, `1` Prüfung oder Schritt fehlgeschlagen, `2` Aufruf/Verweigerung.

## Phasen und Prüfungen

| Phase | Mutiert | Prüfungen (Abbruch bei Fehler) |
|---|---|---|
| `baseline` | Baseline-Datei | Fingerabdruck aus Container-Image-IDs/StartedAt, Compose-Hash, alembic, optionale Invariante (`INVARIANT_SQL`); leere Werte oder fehlende Dienste = Fehler; Überschreiben nur mit `--rebaseline` (prod zusätzlich `--i-am-sure-prod`) |
| `pre` | nein | Compose gültig, Drift gegen Baseline, Marker und HEAD == `--old-sha`, **Backup-Frische** (`BACKUP_MAX_AGE_S`) und sha256, Platz, Readiness; protokolliert alembic-Revision und Image-IDs |
| `prep` | Sicherungen, Tags, Checkout, Build | Sicherung von Compose/Marker/Konfig; **Rollback-Tag == laufende Image-ID** je Dienst; Checkout == `--new-sha` (bei Abbruch zurück auf `--old-sha`); Compose-Diff berührt keine Volumes/Netze/unveränderlichen Dienste; `compose --dry-run` betrifft nur Schreiber, ebenso der Trockenlauf von `run --rm --no-deps migrate` (migrate nutzt die laufende Datenbank, `--no-deps` verhindert das Anfassen von Abhängigkeiten, wie im bewährten Host-Skript); ein `diff`-Fehler ist fail-closed; State bindet `--old-sha`/`--new-sha`; Build; Drift und Unverändertheit von Postgres/Redis/PDF |
| `switch` | Fenster | Voraussetzungen, Timer und Schreiber stoppen, Pre-Deploy-Dump **nach** dem Schreiber-Stopp (mtime ≥ Stoppzeit, `BACKUP_SERVICE` Pflicht, `systemctl start` einer oneshot-Unit ist synchron) + sha256, Compose ersetzen, Migration, **alembic vorher/nachher** und `== --expect-revision`, Invariante unverändert, Recreate, **laufendes Image == in `prep` gebautes Image**, unveränderliche Dienste, Readiness, nach `POST_SWITCH_WAIT_S` keine Tracebacks und `RestartCount` 0; State/SHAs müssen zu `prep` passen; setzt `SWITCH_DONE_AT` |
| `marker` | Marker | `switch` abgeschlossen (State-SHAs == Parameter, `rollback` löscht `SWITCH_OK`), HEAD, Marker == `--old-sha` (nie überschreiben), laufende Images == in `prep` gebaute, Readiness; **Abnahmebericht**: Art `smoke` (prod) bzw. `smoke`/`acceptance` (audit) vom passenden Skript, echter PASS (kein Dry-Run, nicht PARTIAL, kein `skip_llm`), mindestens `MIN_SMOKE_PASS` bestandene Prüfungen, genau Ziel und SHA, jünger als `MAX_SMOKE_AGE_S` und **nach dem switch gestartet**; eigene Release-/Drill-Berichte zählen nie; Marker **atomar** (temp-Datei im selben Verzeichnis, Besitzer/Modus vom alten, `mv -f`) |
| `rollback` | Rückweg | Rollback-Tags und Compose-Sicherung vor dem Stoppen prüfen; Tags nach `:latest`, Compose/Checkout/Marker zurück, Recreate ohne Build; **laufendes Image == Rollback-Tag-ID** je Dienst (Abweichung = Fehler), Readiness |

## Drill

```bash
scripts/release/numra-drill.sh --target audit --config ~/release-audit.env [--dry-run]
```

Stellt den jüngsten Dump in einem privaten Postgres wieder her, migriert auf den Kandidaten
und prüft per HTTP-Sonde zuerst den **alten** Code (Rollback R1) und dann den **neuen** Code
gegen dieselbe Datenbank. Zusätzliche Konfiguration: `DRILL_WORKDIR`, `DRILL_PG_IMAGE`,
`DRILL_REDIS_IMAGE`, `DRILL_OLD_API_IMAGE`, `DRILL_NEW_API_IMAGE`, `DRILL_MIGRATE_IMAGE`
(optional `DRILL_API_PORT`). Aufgeräumt werden nur selbst erzeugte `drill-<lauf>-*`-Ressourcen;
Dump-Kopie und Env-Dateien werden vor dem Löschen geleert. Die Sonde legt ein synthetisches
Konto (`drill-<zufall>@example.com`) an und entfernt es per `delete-all`.

## Berichte

Jeder Lauf schreibt nach `REPORT_DIR` eine Markdown- und eine JSON-Datei (Rechte 0600) mit
Zeitstempel, Ziel, Ziel-SHA, Skriptversion, Prüfumfang, Einzelergebnissen
(PASS/FAIL/SKIP/INFO mit Evidenz), Einschränkungen und Gesamtergebnis, dazu `release.log`.
Ein Hash allein gilt nicht als Nachweis. Berichte enthalten keine Secrets oder PII.

## Ablauf eines Releases (Kurzfassung)

1. `baseline` einmal nach dem letzten stabilen Zustand, danach `pre --dry-run`, dann `pre`.
2. `prep` ohne Downtime; Bericht und Rollback-Tags ansehen.
3. `switch` im Wartungsfenster mit der vorab festgelegten Ziel-Revision.
4. Abnahme gegen das Ziel (Smoke bzw. Acceptance-Lauf mit `--target-sha`), Bericht aufbewahren.
5. `marker` mit genau diesem Bericht. Bei Fehlschlag oder Abweichung `rollback`, danach
   Bericht prüfen.
6. Beobachtungsfenster; die Entscheidung über einen DB-Restore (R2) bleibt eine manuelle
   Freigabe.

## Grenzen

- Funktionale Abnahme leisten die Smoke-/Acceptance-Läufe, nicht diese Skripte.
- `rollback` stellt keine Datenbank wieder her; Migrationen müssen rückwärtskompatibel
  sein (Drill vorab, siehe release-verification.md).
- Kein Locking: Host-Eingriffe seriell durch genau eine Instanz.
- `docker compose --dry-run` benötigt Compose v2 mit dieser Option.
- Tests laufen gegen Attrappen und belegen Logik und Abbruchverhalten, nicht das Verhalten
  einer echten Docker-Umgebung; `prod` wird nie von Tests berührt.

## Tests

```bash
bash scripts/release/tests/test-numra-release.sh
bash scripts/release/tests/test-numra-drill.sh
uv run --no-project --with pytest pytest scripts/ops_report -q
```
