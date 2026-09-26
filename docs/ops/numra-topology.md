# NUMRA — Laufzeit-Topologie auf Agent0 (versioniert, ohne Secrets)

Stand: 2026-09-20. Diese Datei beschreibt **nur** Namen, Rollen und Ports. Keine
Zugangsdaten, keine Tokens, keine Verbindungsstrings — die Werte liegen ausschließlich in
`/etc/numra/*.env` (root, 0600). Historischer Migrationsbericht:
`docs/ops/2026-09-19-hermestrader-to-agent0-migration.md`.

## Die zwei Stacks

| | Produktion | Audit-Instanz |
|---|---|---|
| Compose-Projekt | `numra-prod` | `numra-audit` |
| Verzeichnis | `/opt/numra` | `/opt/numra` |
| Compose-Dateien | `/opt/numra/compose.production.yml` | `/opt/numra/repo/docker-compose.yml` + `/opt/numra/audit-compose.yml` |
| Env-Datei (Werte root-only) | `/etc/numra/numra.env` | `/etc/numra/audit.env` |
| HTTP nach außen | Tailscale `:8443` | Tailscale `:8444` |
| API auf Loopback | `:17800` | `:17801` |
| Datenbank | Container `numra-prod-postgres-1`, DB `numra` | Container `numra-audit-postgres-1`, DB `numra` |
| Sieben `AVENYTH_*`-V2-Flags | aus (Produktentscheidung) | im Overlay erzwungen an (nur so sind die V2-Flows abnehmbar) |
| Zweck | echte Nutzer | ausschließlich synthetische `@example.com`-Konten |

Beide Stacks laufen mit `restart: unless-stopped` und überleben einen Host-Reboot.
Der Checkout `/opt/numra/repo` ist auf einen Commit gepinnt; es gibt **kein**
Auto-Deploy — ein Deploy ist ein bewusster Einzelbefehl (Rezept unten).

## Container

Produktion: `api`, `web`, `worker`, `postgres`, `redis`, `pdf`, dazu der Migrations-
Einmaljob. `analysis-worker` (V2-Jobpipeline) ist seit 2026-09-26 in
`deploy/compose.production.yml` definiert und läuft ab Stufe 0 der V2-Aktivierung
(`docs/ops/2026-09-26-v2-activation-connections-workspaces.md`); bis zum Host-Deploy
läuft er nur im Audit-Stack. Die sieben `AVENYTH_*`-Flags werden ebenfalls durchgereicht
(Default `false`).

Das PDF-Rendering läuft in beiden Stacks als eigener Dienst (Chromium); die
Readiness-Antwort des API enthält dessen Zustand als `pdf`.

## Was wo liegt

| Pfad | Inhalt | Rechte |
|---|---|---|
| `/etc/numra/*.env` | alle Secrets beider Stacks | root, 0600 |
| `/opt/numra/repo` | Git-Checkout der Audit-Instanz (Commit gepinnt) | root |
| `/var/lib/numra/backups` | logische Postgres-Dumps + `.sha256`-Sidecar | root, 0750 (Gruppe `hermes` darf **auflisten**, nicht lesen) |
| `/var/lib/numra/deployed_sha` | Commit, der in Produktion ausgerollt ist | root |
| `/var/lib/numra/health-status.json` | Ergebnis der Readiness-Probe | `hermes` |

## Monitoring und Sicherung

- `numra-healthcheck.timer` (alle 5 min) → `numra-healthcheck.service`. Prüft die
  Readiness beider Stacks über `127.0.0.1:17800/17801/v1/health/ready`, die Frische des
  jüngsten Dumps (Grenze 26 h) und zählt fehlgeschlagene Report-/Analysejobs.
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
sudo git -C /opt/numra/repo fetch origin --prune
sudo git -C /opt/numra/repo checkout "$SHA"
cd /opt/numra && sudo docker compose -p numra-audit --env-file /etc/numra/audit.env \
  -f /opt/numra/repo/docker-compose.yml -f /opt/numra/audit-compose.yml build
sudo docker compose -p numra-audit --env-file /etc/numra/audit.env \
  -f /opt/numra/repo/docker-compose.yml -f /opt/numra/audit-compose.yml up -d
```

Für Produktion dieselbe Sequenz mit `-p numra-prod`, `compose.production.yml` und
`/etc/numra/numra.env`. Vor jeder Änderung an einer Env-Datei liegt eine
`*.bak-pre-<thema>-<zeitstempel>`-Kopie daneben.

## Wiederherstellung

Siehe `docs/audits/2026-09-20-pwa-09-restore-drill.md` (geübter Ablauf inklusive
gemessener Dauer). Kurzfassung: Dump in eine **frische, isolierte** Postgres-Instanz
zurückspielen, Migrationsstand und Zeilenzahlen gegen die Quelle vergleichen, niemals in
die laufende Produktionsdatenbank.
