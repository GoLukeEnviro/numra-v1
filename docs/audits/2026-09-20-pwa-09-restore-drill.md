# PWA-09 — Restore-Drill der Produktionssicherung (2026-09-20)

Ziel: beweisen, dass die nächtliche Sicherung im Ernstfall **wirklich** zurückgespielt
werden kann — nicht nur, dass sie geschrieben wird. Der Drill lief ausschließlich gegen
ein Wegwerf-Ziel; die laufende Produktionsdatenbank wurde nur **gelesen** (Zeilenzahlen,
Fingerabdrücke), nie beschrieben.

## Vorgehen

1. Sicherung wählen: `/var/lib/numra/backups/numra-20260920T011605Z.dump` (jüngster
   Dump, 03:16 lokal / 01:16 UTC), Prüfsumme über den Sidecar verifiziert.
2. Isoliertes Ziel starten: frischer Container `numra-drill-pg`
   (`postgres:16-alpine`, **kein** veröffentlichter Port, eigenes Zufallspasswort) —
   bewusst ein anderer Serverprozess als Produktion und als die Testdatenbank.
3. `pg_restore --exit-on-error --no-owner --no-privileges` in die leere Datenbank,
   Dauer gemessen.
4. Vergleich Quelle ↔ Wiederherstellung: Migrationsstand, Tabelleninventar,
   Zeilenzahlen, ein Inhalts-Fingerabdruck sowie referenzielle Integrität.
5. Ziel verwerfen.

## Ergebnis

| Prüfgröße | Produktion | Wiederherstellung | Bewertung |
|---|---|---|---|
| Integrität der Datei (`sha256sum -c`) | — | `OK` | ✓ |
| Bereitschaft des Ziels | — | 2 s | ✓ |
| Dauer des `pg_restore` | — | **1,07 s** | ✓ |
| Migrationsstand (`alembic_version`) | `e6a1b2c3d4e5` | `e6a1b2c3d4e5` | ✓ = Repo-Head |
| Tabellen im Schema `public` | 50 | 50 | ✓ Inventar identisch |
| Fremdschlüssel / Indizes | 90 / 151 | 90 / 151 | ✓ |
| Verwaiste Zeilen (Reports/Sections/People) | 0 | 0 | ✓ |
| Fingerabdruck `calculations.deterministic_hash` | `d0b75ec4c9c1eb237a309cf86eea5642` | identisch | ✓ |
| Zeilenzahlen (Auszug) | people 4, calculations 5, reports 13, report_sections 42, analysis_jobs 0, checkin_responses 0 | identisch | ✓ |
| `users` | 4 | 3 | erwartet, siehe unten |

**Der einzige Unterschied ist erklärbar:** Produktion enthält heute vier `users`-Zeilen,
der Dump drei. Die vierte ist ein Grabstein eines synthetischen Kontos, das am
2026-09-20 um 04:13 UTC angelegt und um 04:17 UTC gelöscht wurde (also **nach** der
Sicherung um 01:16 UTC). Genau dieses Verhalten ist gewollt: die Sicherung ist ein
Zeitschnitt, kein Live-Spiegel.

Der Fingerabdruck der Rechenergebnisse ist bewusst ein Hash über die vorhandenen
`deterministic_hash`-Werte und keine Datenkopie — der Nachweis „die Nutzdaten sind
vollständig da“ gelingt damit ohne personenbezogene Inhalte im Audit-Artefakt.

## Bewertung und Grenzen

- Die Sicherung ist **wiederherstellbar** und auf dem aktuellen Migrationsstand; ein
  `alembic upgrade head` ist nach dem Zurückspielen nicht nötig.
- Gemessene Wiederherstellungszeit für den reinen Restore: ~1 s bei ~300 KB Dump. Das ist
  keine Aussage über einen Produktions-RTO bei voller Datenmenge — die aktuelle Datenbank
  ist klein (synthetische Konten). Die Aussage dieses Drills ist „der Ablauf funktioniert
  und das Artefakt ist vollständig“, nicht „der RTO beträgt eine Sekunde“.
- Die Sicherung ist ein logischer Dump, kein PITR: Der Datenverlust im Katastrophenfall
  ist bis zu 24 h (bis zur nächsten 03:16-Sicherung).
- Offsite: `restic-agent0-backup` überträgt seit 2026-09-20 auch `/etc/numra` (Deployment-
  Konfiguration) und `/var/lib/numra` (die Dumps selbst) verschlüsselt nach Backblaze B2;
  vorher lagen beide nur auf diesem Host.
- Die **Audit**-Datenbank wird bewusst nicht gesichert: sie enthält ausschließlich
  synthetische Daten und wird nach der Abnahme verworfen.
- Nicht Teil dieses Drills: Wiedereinspielen in eine echte Ersatzumgebung mit laufendem
  API und Datenverkehr (Fire-Drill). Das bleibt ein bewusster, manueller Schritt der
  Betriebsübergabe — das Rezept steht in `docs/ops/numra-topology.md`.

## Reproduktion

```bash
# 1. Datei prüfen
sudo sha256sum -c /var/lib/numra/backups/numra-<zeitstempel>.dump.sha256

# 2. isoliertes Ziel
docker run -d --name numra-drill-pg -e POSTGRES_USER=numra -e POSTGRES_DB=numra \
  -e POSTGRES_PASSWORD="$(openssl rand -hex 16)" postgres:16-alpine

# 3. zurückspielen (--exit-on-error lässt den Lauf bei Teilfehlern scheitern)
sudo cat /var/lib/numra/backups/numra-<zeitstempel>.dump \
  | docker exec -i numra-drill-pg pg_restore -U numra -d numra --no-owner --no-privileges --exit-on-error

# 4. vergleichen (Zahlen/Fingerabdrücke, keine Zeilendaten)
docker exec -i numra-drill-pg psql -U numra -d numra -c \
  "select version_num from alembic_version; select count(*) from information_schema.tables where table_schema='public';"

# 5. verwerfen
docker rm -f numra-drill-pg
```
