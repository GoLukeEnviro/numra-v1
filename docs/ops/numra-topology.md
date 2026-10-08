# NUMRA — Laufzeit-Topologie auf Agent0 (versioniert, ohne Secrets)

Stand: 2026-10-08. Diese Datei beschreibt **nur** Namen, Rollen und Ports. Keine
Zugangsdaten, keine Tokens, keine Verbindungsstrings — die Werte liegen ausschließlich in
`/etc/numra/*.env` (root, 0600). Historischer Migrationsbericht:
`docs/ops/2026-09-19-hermestrader-to-agent0-migration.md`.

## Die zwei Stacks

| | Produktion | Audit-Instanz |
|---|---|---|
| Compose-Projekt | `numra-prod` | `numra-audit` |
| Verzeichnis | `/opt/numra` | `/opt/numra` |
| Compose-Dateien | `/opt/numra/compose.production.yml` | `/opt/numra/audit-repo/docker-compose.yml` + `/opt/numra/audit-compose-s1.yml` (Host-Overlay; das ältere `/opt/numra/audit-compose.yml` bleibt als Rückrollweg) |
| Env-Datei (Werte root-only) | `/etc/numra/numra.env` | `/etc/numra/audit.env` |
| HTTP nach außen | Tailscale `:8443` | Tailscale `:8444` |
| API auf Loopback | `:17800` | `:17801` |
| Datenbank | Container `numra-prod-postgres-1`, DB `numra` | Container `numra-audit-postgres-1`, DB `numra` |
| Sieben V2-Flags (DB-Tabelle `feature_flags`) | Profil `NUMRA_FLAGS_PROFILE` beim ersten Init (kein Default; Bestands-DB: unverändert übernommen) | Profil `audit-all-on` (alle sieben an, Status `bootstrap`; gemessen 2026-10-08) |
| Zweck | echte Nutzer | ausschließlich synthetische `@example.com`-Konten |

Beide Stacks laufen mit `restart: unless-stopped` und überleben einen Host-Reboot.
Die Checkouts `/opt/numra/repo` (Produktion) und `/opt/numra/audit-repo` (Audit) sind je auf einen Commit gepinnt; es gibt **kein**
Auto-Deploy — ein Deploy ist ein bewusster Einzelbefehl (Rezept unten).

## Container

Produktion: `api`, `web`, `worker`, `postgres`, `redis`, `pdf`, dazu die Einmaljobs
`migrate` (Alembic) und danach `flags-init` (siehe „Feature-Flags: Init-Schritt“); `api`
startet erst, wenn beide erfolgreich beendet sind. `analysis-worker` (V2-Jobpipeline) ist seit 2026-09-26 in
`deploy/compose.production.yml` definiert und läuft ab Stufe 0 der V2-Aktivierung
(`docs/ops/2026-09-26-v2-activation-connections-workspaces.md`); bis zum Host-Deploy
läuft er nur im Audit-Stack. Die `AVENYTH_*_ENABLED`-Variablen sind deprecated und ohne
Wirkung (Quelle der Wahrheit ist die DB, siehe unten).

Das PDF-Rendering läuft in beiden Stacks als eigener Dienst (Chromium); die
Readiness-Antwort des API enthält dessen Zustand als `pdf`.

## Was wo liegt

| Pfad | Inhalt | Rechte |
|---|---|---|
| `/etc/numra/*.env` | alle Secrets beider Stacks | root, 0600 |
| `/opt/numra/repo` | Git-Checkout der Produktion (detached auf `deployed_sha`) | hermes |
| `/opt/numra/audit-repo` | Git-Checkout der Audit-Instanz (Commit gepinnt, Marker `/var/lib/numra/audit_deployed_sha`) | hermes |
| `/var/lib/numra/backups` | logische Postgres-Dumps + `.sha256`-Sidecar | root, 0750 (Gruppe `hermes` darf **auflisten**, nicht lesen) |
| `/var/lib/numra/deployed_sha` | Commit, der in Produktion ausgerollt ist | root |
| `/var/lib/numra/health-status.json` | Ergebnis der Readiness-Probe | `hermes` |
| DB-Tabelle `feature_flags` (`numra`-DB) | Laufzeitwert der sieben V2-Flags -- einzige Quelle der Wahrheit (`/admin/flags`); die `AVENYTH_*_ENABLED`-Env-Vars sind deprecated und wirkungslos | ueber `/admin/flags` (Rolle ADMIN) oder direkt per SQL |
| DB-Tabelle `feature_flag_bootstrap` (`numra`-DB) | Singleton-Status des einmaligen Flag-Inits (`bootstrap` oder `adopted`, Profil, Zeitpunkt) | nur durch Migration bzw. `flags init` |

## Feature-Flags: Init-Schritt

Flag-Werte entstehen **nicht** aus Env-Variablen, sondern aus der DB. Neue Umgebungen
werden einmalig initialisiert; danach ändert nur noch `/admin/flags` Werte.

- Befehl: `python -m numra_api.cli flags init [--profile <all-off|beta|audit-all-on>] [--dry-run]`
  (in Produktion als Einmaljob `flags-init` nach `migrate`; ohne `--profile` gilt
  `NUMRA_FLAGS_PROFILE` aus der Env-Datei, **kein Default-Profil**).
- Profil ist nur nötig, solange der Status fehlt. Fehlt er und es ist kein Profil gesetzt
  (z. B. nach Restore/`alembic stamp`), bricht `init` mit Exit 2 ab, schreibt nichts und
  `api` startet nicht. Mit vorhandenem Status und `--dry-run` geht es auch ohne Profil;
  eine Bestands-DB scheitert nie am fehlenden Env.
- Profile liegen versioniert in `apps/api/src/numra_api/feature_flag_profiles.py`:
  `all-off` (7 aus), `beta` (`v2_master`, `connections`, `relationship_workspaces`,
  `copilot` an), `audit-all-on` (7 an).
- Entscheidend ist allein die Singleton-Zeile in `feature_flag_bootstrap`. Existiert sie,
  ist `init` ein No-op (auch mit anderem Profil, dann nur ein Hinweis im Log). Fehlt sie,
  werden Profilwerte und Status in einer Transaktion gesetzt; konkurrierende Inits wirken
  nur einmal. Jede Änderung wird als `FEATURE_FLAG_CHANGED` mit `actor_user_id = NULL`
  und `origin = bootstrap` auditiert.
- Bestands-DBs: stand `feature_flags` (Migration `04d4d6f4c5a0`) schon VOR dem
  Alembic-Lauf, legt `7c3e9a51b2d8` den Status `adopted` / Profil `pre-existing` an; Werte
  und `updated_at` bleiben unverändert. Frische DBs (Lauf startet leer oder vor `04d4`)
  bekommen keinen Status: die Seed-Zeilen von `04d4` stammen dann aus demselben Lauf, und
  `flags init` setzt das Profil. Die Startrevisionen legt `alembic/env.py` in
  `config.attributes["starting_heads"]` ab (die Versionstabelle wird während des Laufs
  fortgeschrieben, ein Skript kann den Startzustand sonst nicht mehr lesen). Fehlt der
  Eintrag, gilt fail-safe `adopted`.
- `--dry-run` zeigt Status und Diff und schreibt nichts.
- Dev-/CI-Compose (`docker-compose.yml`): bewusst **ohne** `flags-init`-Job. Dort wirken
  die Seed-Werte von `04d4` (4 an: `v2_master`, `connections`, `relationship_workspaces`,
  `copilot`; kein Status). Alle sieben an: manuell
  `docker compose exec api python -m numra_api.cli flags init --profile audit-all-on`.
- RC2-Journey-Stack (`docker-compose.rc2.yml`, Workflow `rc2-journey.yml`): hat einen
  eigenen `flags-init`-Job mit Profil `audit-all-on` nach `migrate`, `api` wartet darauf.
  Ohne ihn blieben `checkins`, `tasks` und `evidence_layer` auf der frischen DB aus und die
  Journey scheiterte an den 503-Seiten. Die `AVENYTH_*`-Variablen dort wurden entfernt
  (seit #271 wirkungslos).
- **E3-Vorbereitung Audit-Stack** (Host-Overlay `/opt/numra/audit-compose.yml`, nicht Teil
  dieses Repos/PRs): `NUMRA_FLAGS_PROFILE=audit-all-on` in `/etc/numra/audit.env` setzen und
  einen `flags-init`-Job nach `migrate` ergänzen; die `AVENYTH_*`-Variablen im Overlay
  entfernen (wirkungslos). Die Audit-DB stand vor `04d4d6f4c5a0` und hat daher
  den Status `bootstrap` (Profil `audit-all-on`, gemessen 2026-10-08), nicht `adopted`.

## Monitoring und Sicherung

- `numra-healthcheck.timer` (alle 5 min) → `numra-healthcheck.service`. Prüft die
  Readiness beider Stacks über `127.0.0.1:17800/17801/v1/health/ready`, die Frische des
  jüngsten Dumps (Grenze 26 h) und zählt fehlgeschlagene Report-/Analysejobs. Die
  Readiness wird je Dienst gegen `EXPECTED_DEPENDENCIES` bewertet (Alarm ab 3
  aufeinanderfolgenden Fehlschlägen, Details: `docs/ops/numra-monitoring.md`).
  Schreibt `/var/lib/numra/health-status.json`; ein Fehlschlag lässt die Unit in
  `systemctl --failed` auftauchen. Skript: `scripts/ops/numra-healthcheck.sh`.
- `numra-backup.timer` (täglich 03:16 lokal) → `numra-backup.sh`: `pg_dump -Fc` der
  Produktions-DB nach `/var/lib/numra/backups`, Aufbewahrung 14 Tage, Prüfsumme daneben.
- `restic-agent0-backup.timer` (täglich) sichert offsite nach Backblaze B2 — seit
  2026-09-20 einschließlich `/etc/numra` und `/var/lib/numra`, damit Deployment-
  Konfiguration und logische Dumps einen Hostverlust überleben. Clientseitig
  verschlüsselt (`restic`), Aufbewahrung 7 täglich / 4 wöchentlich / 6 monatlich.
  Wöchentlicher Integritätscheck: `restic-agent0-check.timer`.

**Nicht** abgedeckt: Es gibt keinen externen Pager/Alertkanal. Der sichtbare Alarm ist
die fehlgeschlagene Unit plus die Statusdatei; die Audit-Datenbank wird bewusst nicht
gesichert (Wegwerfdaten, siehe `docs/audits/2026-09-20-pwa-09-restore-drill.md`).

## Deploy-Rezept (bewusster Einzelbefehl)

```bash
SHA=<commit>
sudo git -C /opt/numra/audit-repo fetch origin --prune
sudo git -C /opt/numra/audit-repo checkout "$SHA"
cd /opt/numra && sudo docker compose -p numra-audit --project-directory /opt/numra/audit-repo \
  --env-file /etc/numra/audit.env \
  -f /opt/numra/audit-repo/docker-compose.yml -f /opt/numra/audit-compose-s1.yml build
sudo docker compose -p numra-audit --project-directory /opt/numra/audit-repo \
  --env-file /etc/numra/audit.env \
  -f /opt/numra/audit-repo/docker-compose.yml -f /opt/numra/audit-compose-s1.yml up -d
```

`up -d` startet über `depends_on` zuerst `migrate`, dann `flags-init`; `api` wartet auf beide.
Für Produktion dieselbe Sequenz mit `-p numra-prod`, dem Checkout `/opt/numra/repo`,
`/opt/numra/compose.production.yml` und `/etc/numra/numra.env`. Vor jeder Änderung an einer Env-Datei liegt eine
`*.bak-pre-<thema>-<zeitstempel>`-Kopie daneben.

## Wiederherstellung

Siehe `docs/audits/2026-09-20-pwa-09-restore-drill.md` (geübter Ablauf inklusive
gemessener Dauer). Kurzfassung: Dump in eine **frische, isolierte** Postgres-Instanz
zurückspielen, Migrationsstand und Zeilenzahlen gegen die Quelle vergleichen, niemals in
die laufende Produktionsdatenbank.
