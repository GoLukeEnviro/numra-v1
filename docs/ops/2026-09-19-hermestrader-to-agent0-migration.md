# NUMRA migration HermesTrader → agent0 — execution report

> Repository copy of the operator-side migration report. Source: `/home/hermes/reports/numra-agent0-migration-report-20260919.md` (this host, 2026-09-19). Sanitization check before import: zero credential assignments, zero bearer tokens; the file records paths, commands and verification results only. Host-local paths and the operator decision notes are kept verbatim because they are the audit trail for the cutover.

**Datum:** 2026-09-19 · **Status:** Produktion migriert und verifiziert; Audit-Stack im Aufbau
**Grundlage:** `numra-agent0-migration-plan-20260918.md`, Bundle `numra-transfer.tgz` (SHA `c4c18954…`)

---

## 1. Was übertragen wurde — und was bewusst nicht

| Objekt | Ergebnis |
|---|---|
| **Postgres (alle Produktivdaten)** | übertragen per `pg_dump -Fc` → Restore auf agent0 |
| **Export-Volume** | übertragen (1 gerendertes PDF, 116.786 Bytes) |
| **Deployment-Definition** | rekonstruiert aus der entschärften Original-Compose; Struktur-Parität maschinell geprüft |
| **Secrets** | **neu erzeugt** auf agent0 (SESSION_SECRET, POSTGRES_PASSWORD, PDF_INTERNAL_TOKEN) — Originale nie gelesen |
| **Redis-Inhalt** | bewusst nicht übertragen (flüchtig) |
| **Auto-Deploy-Timer** | bewusst **nicht** übernommen (Doppelbetriebs-Risiko) — manueller, bewusster Deploy |

## 2. Empfangs-Verifikation des Bundles

Ein Bundle belegt Transport, nicht Tauglichkeit — geprüft wurde deshalb beides:

| Prüfung | Ergebnis |
|---|---|
| Pfad-Sicherheitsscan (absolut / `..` / Links) | 17 Members, **0 unsicher** |
| `numra.dump` SHA-256 | **MATCH** (`fd611074…`) gegen Sidecar |
| `exports.tgz` SHA-256 | **MATCH** (`9595fdf4…`) |
| Compose-Scrub SHA-256 | **MATCH** (`5437a033…`) |
| Maskierungs-Gate (Credential-Zeile ohne `***`) | **PASS** — ausschließlich `***`-Zeilen |
| Dump-Struktur | valide, Format CUSTOM, PG 16.15, 50 Tabellen |
| Manifest-Abgleich | `repo_head = origin_main = deployed_sha = f522067e…` — identisch mit dem lokalen Clone |

**Restore-Trockenlauf** (frische Wegwerf-DB auf agent0):
`restore stderr: 0 Zeilen` · 50 Tabellen · **alle Zeilenzahlen identisch** · Alembic `e6a1b2c3d4e5` · danach entfernt.

## 3. Zielumgebung auf agent0

| Ding | Wert |
|---|---|
| Deployment-Checkout | `/opt/numra/repo` @ `f522067e8521d78335b3a4c3ec75739809ce1a32` (gepinnt) |
| Compose | `/opt/numra/compose.production.yml` (secret-frei, `${VAR}`-Platzhalter) |
| Env | `/etc/numra/numra.env`, Modus `600` |
| `deployed_sha` | `/var/lib/numra/deployed_sha` = `f522067e…` |
| Volumes | `numra_prod_postgres_data`, `numra_prod_exports_data` |
| Ports | API `127.0.0.1:17800`, Web `127.0.0.1:17300` |
| Zugang | `https://agent0-1.taile6801f.ts.net:8443` (tailnet-only) |

## 4. Verifikation der laufenden Produktion

| Prüfung | Ergebnis |
|---|---|
| Container | api/web/pdf/postgres/redis healthy, worker up, migrate `Exited (0)` |
| Migration | `alembic upgrade head` lief sauber (No-op: DB bereits auf `e6a1b2c3d4e5` = Head) |
| **Zeilenzahlen** | **50/50 Tabellen identisch zur Quelle, 0 Mismatches** |
| `/v1/health/ready` | `{"status":"healthy","database":"healthy","numerology_engine":"healthy","llm":"disabled","pdf":"healthy"}` |
| Web | `:17300/login` → 200; Login-Seite rendert (Browser geprüft, Screenshot) |
| API durch den Web-Proxy | `/api/v1/health/ready` → healthy (der Pfad, den der Browser nimmt) |
| Login-Endpoint | POST ohne Body → 422 (korrekte Validierung, kein 5xx) |
| Export-Volume | restauriert, PDF vorhanden |
| Datenbestand | 3 User, 4 People, 13 Reports, 42 Report-Sections, 74 Sessions — identisch zur Quelle |

**Kein Container desselben Projekts läuft doppelt:** `numra-prod` existiert nur auf agent0 (HermesTrader läuft weiter, bis Luke den Stopp freigibt).

## 5. Backup (Teil der Fertigstellung, nicht optional)

HermesTrader hatte `numra-backup.timer` — agent0 ist nicht schlechter:

- `/usr/local/bin/numra-backup.sh` · Unit + Timer `numra-backup.{service,timer}`
- Zeitplan `01:16 UTC` (dasselbe Fenster wie HermesTrader), `Persistent=true`
- **Beweis statt Absicht:** Timer einmal manuell ausgelöst → Dump `numra-20260919T142616Z.dump` (300.569 Bytes, exakt quellgleich), `pg_restore --list` valide, Retention 14 Tage.

## 6. Der einzige verbleibende Unterschied (bewusst)

`HERMESTRADER (alt)`: Auto-Deploy-Timer (`numra-update.timer`, alle ~5 min) → deployte jeden Merge
`AGENT0 (neu)`: **kein** Auto-Deploy; Deploy ist ein bewusster Einzelbefehl

Ein blinder Auto-Deploy-Loop während des Doppelbetriebs wäre automatische Doppelausführung. Nach Lukes Freigabe zur Stilllegung des Alt-Stacks kann ein Timer mit denselben Gates nachgezogen werden.

## 7. Offene Operator-Entscheidung

Der Alt-Stack auf HermesTrader ist **unangetastet** (läuft weiter). Stilllegung braucht Lukes separate Freigabe — erst dann:

1. `numra-prod` auf HermesTrader stoppen (kein `down -v` — Volumes bleiben als Rückfall)
2. Serve-Mapping `:8443`/`:8444` dort entfernen
3. agent0 behält `:8443` (Prod) und erhält `:8444` (Audit)

## 8. Audit-Stack auf agent0 — läuft, und besser als das Original

Der Audit-Stack läuft als Projekt `numra-audit` (eigene Env `/etc/numra/audit.env` mit
frischen Secrets, Overlay `/opt/numra/audit-compose.yml`), erreichbar über
`https://agent0-1.taile6801f.ts.net:8444`. **Alle 8 Container healthy** — inklusive
`analysis-worker`, dessen Fehlen auf HermesTrader den PWA-04-Remote-Befund #2
(„Analyse bleibt Queued") verursacht hat.

Besonderheiten des Overlays (alle begründet):
- alle 7 `AVENYTH_*`-Flags an, `ENVIRONMENT=test` + `EMAIL_BACKEND=logging` (kein echter
  Mailversand), `NUMRA_LLM_PROVIDER=mock` (deterministisch für die Abnahme),
- postgres/redis/pdf **nicht** veröffentlicht; nur api (17801) und web (17301) auf Loopback,
- `HOSTNAME: 0.0.0.0` für den Next.js-Container — ohne das bindet Next.js-Standalone an den
  Container-Hostnamen und der eingebaute Healthcheck schlägt fehl, obwohl der Port von außen
  erreichbar ist (das Prod-Compose setzt ihn, das Basis-Compose nicht).

## 9. End-to-End-Beweis: PWA-04-Abnahme gegen die neue Instanz

Der vollständige Zwei-Account-Journey lief **gegen die agent0-Audit-Instanz** (nicht lokal):

```text
RC2_BASE_URL=https://agent0-1.taile6801f.ts.net:8444 RC2_MSG_PREFIX=AUDIT-AGENT0 \
  npx playwright test --config=playwright.rc2.config.ts
→ 2 passed (1.4m), AUDIT_REMOTE_EXIT=0
```

- Beide Viewports (1440×900, 390×844) grün, 38 Screenshots, eigener Workspace je Lauf.
- **Der frühere Remote-Blocker ist weg:** alle 3 `analysis_jobs` enden `COMPLETE`
  (der `analysis-worker` holt die Jobs ab — vorher blieb genau das aus).
- Erzeugte synthetische Accounts: `system-e2e-rc2-{a,b}-1789828…@example.com`
  (in die PWA-01-Cleanup-Inventarliste aufzunehmen — noch **nicht** löschen).
- **Prod unberührt nachgewiesen:** `users=3, analysis_jobs=0` — der Lauf hat ausschließlich
  die Audit-DB angefasst.

Der Register-Rate-Limiter (Remote-Befund #1) ist lokal sofort rücksetzbar:
`docker exec numra-audit-redis-1 sh -lc 'redis-cli --scan --pattern "auth:*" | while read -r k; do redis-cli del "$k" >/dev/null; done'`

## 10. Verbleibende Operator-Entscheidung

Der Alt-Stack auf HermesTrader läuft **unangetastet** weiter. Für die Stilllegung:

1. Stopp von `numra-prod` und `numra-audit` auf HermesTrader (kein `down -v` —
   Volumes bleiben als Rückfall), Serve-Mappings `:8443`/`:8444` dort entfernen,
2. danach optional einen `numra-update`-Timer auf agent0 nachziehen (mit denselben
   Gates), wenn Luke wieder Auto-Deploy will.

Bis dahin gilt: agent0 ist die neue Primärinstanz, HermesTrader ist der Rückfall.
Kein Container desselben Projekts läuft gleichzeitig auf beiden Hosts als „aktiv" —
beide sind nur deshalb parallel an, weil der Cutover bewusst nach Freigabe erfolgt.
