# Runbook: Stufenweise V2-Aktivierung — Connections und Relationship Workspaces

**Stand:** 2026-09-26 · **Gilt für:** Produktion `numra-prod` auf agent0 (`docs/ops/numra-topology.md`)
**Status:** vorbereitet, **nicht ausgeführt**. Jede Stufe ist ein bewusster Operator-Schritt.
**Werkzeuge:** `deploy/compose.production.yml` (analysis-worker und Flag-Durchreichung), `scripts/ops/v2-flag-probe.sh` (anonymer, schreibfreier Flag-Nachweis)

---

## 1. Worum es geht

Alle sieben `AVENYTH_*`-Flags sind in Produktion aus. Deshalb antworten `/v1/connections`, `/v1/workspaces` und `/v1/me/copilot/threads` heute mit `503 V2_DISABLED` (live gemessen am 26.09.2026). Der Code ist im Audit-Stack abgenommen (PWA-04: Zwei-Account-Journey, PWA-07: Dissolution/Retention).

Dieses Runbook schaltet **nur** frei:

| Stufe | Flags an | Wird nutzbar |
|---|---|---|
| **0** | keine | nur Infrastruktur: `analysis-worker` läuft, Flags werden durchgereicht; für Nutzer ändert sich nichts |
| **1** | `AVENYTH_V2_ENABLED` | persönlicher Workspace: `/v1/me/workspace`, Private Notes, Private Reflections, Personal Tasks (alle `require_v2_master()`) |
| **2** | + `AVENYTH_CONNECTIONS_ENABLED` + `AVENYTH_RELATIONSHIP_WORKSPACES_ENABLED` | Einladungen (Link/Code/E-Mail-gebunden), Redeem, Connections, Consent, Relationship Workspace (Overview, Dual Profile, Shared Reflections, Relationship-Analyse, Shadow Dynamics), Dissolution |

**Bleiben aus:** `CHECKINS`, `TASKS` (inkl. Roadmaps), `COPILOT`, `EVIDENCE_LAYER`. Die UI zeigt für diese Tabs den ruhigen `PhaseDisabledState` (`components/ui/states.tsx`), keinen Fehler.

## 2. Kopplungen, die die Reihenfolge bestimmen

1. **Das Master-Flag öffnet den persönlichen Workspace.** Das ist Stufe 1 und läuft unabhängig von Connections.
2. **Connections und Relationship Workspaces gehören zusammen.** `redeem_invitation` (`services/connection_service.py:150-190`) legt atomar Connection, Workspace, zwei Member und 6×2 Default-Consent-Grants an. Mit Connections allein entstünden Workspaces, deren Seiten `V2_PHASE_DISABLED` zeigen. Consent hängt am Connections-Flag (`routes/consent.py:28`), der Workspace am Workspace-Flag.
3. **Die Relationship-Analyse und Shadow Dynamics hängen am Workspace-Flag** (`routes/relationship_analysis.py:45`). Sie brauchen den **analysis-worker** und einen **echten LLM-Provider**. Mit `NUMRA_LLM_PROVIDER=disabled` endet jeder Analyse-Job als `FAILED/LLM_PROVIDER_ERROR`, und jeder davon löst im Healthcheck einen Alarm aus.
4. **Entitlements werden serverseitig nicht erzwungen.** `beta_default` schaltet alles frei, und kein Service prüft `connections` oder `max_connections`. Ein Flag gilt deshalb **für alle Nutzer gleichzeitig**. Einen Whitelist-Rollout gibt es erst mit Auftrag **A4** (`docs/planning/2026-09-26-p0-agent-work-orders.md`).
5. **Keine künstlichen Test-Accounts in Produktion** (`docs/ops/release-verification.md`, Regeln). Die Zwei-Account-Abnahme in Stufe 2 braucht zwei **reale** Konten (Operator plus eine vertraute zweite Person).

## 3. Go/No-Go vor Stufe 1 und Stufe 2

| # | Gate | Nachweis | Pflicht für |
|---|---|---|---|
| G1 | `/impressum` und `/datenschutz` liefern 200 ohne Login; die Datenschutzerklärung nennt Partnerdaten, Consent-Modell, LLM-Anbieter, Resend und Cloudflare | `curl -s -o /dev/null -w '%{http_code}' https://avenyth.de/impressum` | Stufe 1 |
| G2 | Error Boundaries und Client-Timeout live (Auftrag A5) | Deploy-SHA enthält den PR | Stufe 1 |
| G3 | Redeem von `EMAIL`-Einladungen nur durch die eingeladene, **verifizierte** Adresse; Einladungen erstellen und einlösen nur mit verifizierter E-Mail (Auftrag A3) | Integrationstests grün, Deploy-SHA | Stufe 2 |
| G4 | KI-Hinweis an Dynamics- und Analyse-Ergebnissen (Auftrag A2) | UI-Check | Stufe 2 |
| G5 | Healthcheck erkennt hängende `QUEUED`-Analysejobs (Auftrag A6) | `/var/lib/numra/health-status.json` enthält `prod_stale_queued_jobs` | Stufe 2 |
| G6 | LLM-Provider-Entscheidung: der Log des `analysis-worker` zeigt `llm_provider=<Klasse>` ≠ `DisabledLLMProvider`, **oder** es ist bewusst entschieden, dass Dynamics vorerst fehlschlägt | `docker compose … logs analysis-worker \| grep "analysis worker starting"` | Stufe 2 |
| G7 | LLM-Call-Log aktiv (Auftrag A7) **oder** Kostenrisiko für Dynamics bewusst akzeptiert (Rate-Limits sind vorhanden) | Deploy-SHA | Stufe 2 |
| G8 | Jüngstes Backup < 26 h | `ls -t /var/lib/numra/backups \| head -1` | jede Stufe |
| G9 | Zweite reale Person für die Abnahme verfügbar | – | Stufe 2 |

## 4. Gemeinsame Befehle

```bash
# Immer explizit (release-verification.md):
DC="docker compose -p numra-prod --env-file /etc/numra/numra.env -f /opt/numra/compose.production.yml"

# Env-Änderung mit Zeitstempel-Backup (Muster aus 2026-09-25-production-smtp-cors-signup.md)
sudo cp -p /etc/numra/numra.env "/etc/numra/numra.env.bak.$(date +%Y%m%dT%H%M%S)"

# Nur die Flag-Namen und Werte prüfen, niemals die ganze Datei ausgeben:
sudo grep -E '^AVENYTH_' /etc/numra/numra.env || echo "keine AVENYTH_-Zeilen"

# Anonymer Flag-Nachweis (öffentlich und host-lokal):
/opt/numra/repo/scripts/ops/v2-flag-probe.sh https://avenyth.de/api stageN
/opt/numra/repo/scripts/ops/v2-flag-probe.sh http://127.0.0.1:17800 stageN
```

Flags wirken nur im `api`-Prozess (`services/feature_flags.py`). Nach einer Env-Änderung reicht deshalb:

```bash
$DC up -d --no-deps --force-recreate api
```

## 5. Stufe 0: Infrastruktur (verhaltensneutral)

1. Den PR `ops/v2-activation-prep` mergen und nach `release-verification.md` deployen (SHA-Gate, Alembic-Gate).
2. Die versionierte Compose-Datei auf den Host übernehmen (die Host-Datei ist die, die tatsächlich läuft):
   ```bash
   sudo cp -p /opt/numra/compose.production.yml "/opt/numra/compose.production.yml.bak.$(date +%Y%m%dT%H%M%S)"
   sudo cp /opt/numra/repo/deploy/compose.production.yml /opt/numra/compose.production.yml
   $DC config --quiet && echo "compose OK"
   ```
3. Den analysis-worker starten:
   ```bash
   $DC up -d --build analysis-worker
   $DC ps analysis-worker
   $DC logs --tail 20 analysis-worker | grep "analysis worker starting"   # zeigt llm_provider=… (G6)
   ```
4. Nachweis:
   ```bash
   scripts/ops/v2-flag-probe.sh https://avenyth.de/api stage0     # RESULT: OK (matches stage0)
   ```
5. Execution-State: `V2_STAGE=0 (infra), analysis-worker running, llm_provider=<…>`.

## 6. Stufe 1: Master-Flag (persönlicher Workspace)

1. Gates G1, G2 und G8 abhaken.
2. In `/etc/numra/numra.env` (Backup vorher, siehe §4):
   ```bash
   AVENYTH_V2_ENABLED=true
   ```
3. `$DC up -d --no-deps --force-recreate api`
4. Nachweis: `scripts/ops/v2-flag-probe.sh https://avenyth.de/api stage1`
5. Manuelle Abnahme mit dem eigenen Konto:
   - `/people/<id>/workspace` öffnen, eine Private Note, eine Reflection und einen Personal Task anlegen, bearbeiten und löschen
   - `/connections` und `/workspaces` zeigen den ruhigen „nicht freigeschaltet"-Zustand, keinen Fehler
6. **Beobachtung 24–48 h:** keine 5xx-Häufung (`$DC logs --since 24h api | grep -c '" 5[0-9][0-9] '`), keine neuen Healthcheck-Alarme.
7. Execution-State: `V2_STAGE=1`.

## 7. Stufe 2: Connections und Relationship Workspaces

1. Gates G1–G9 abhaken.
2. In `/etc/numra/numra.env`:
   ```bash
   AVENYTH_V2_ENABLED=true
   AVENYTH_CONNECTIONS_ENABLED=true
   AVENYTH_RELATIONSHIP_WORKSPACES_ENABLED=true
   # bleiben ausdrücklich false:
   AVENYTH_CHECKINS_ENABLED=false
   AVENYTH_TASKS_ENABLED=false
   AVENYTH_COPILOT_ENABLED=false
   AVENYTH_EVIDENCE_LAYER_ENABLED=false
   ```
3. `$DC up -d --no-deps --force-recreate api`
4. Nachweis: `scripts/ops/v2-flag-probe.sh https://avenyth.de/api stage2`
5. **Zwei-Konten-Abnahme** mit realen Konten A (Operator) und B (vertraute Person), beide mit verifizierter E-Mail:

   | # | Schritt | Erwartung |
   |---|---|---|
   | 1 | A: `/connections/invite`, Methode **Link** | Link und Code erscheinen, Einladung `PENDING` in der Liste |
   | 2 | B: Link öffnen, anmelden, Vorschau prüfen, annehmen | Connection `ACTIVE`, Weiterleitung in den Workspace |
   | 3 | A und B: `/workspaces/<id>` | Overview und Dual Profile zeigen beide Profile, **kein Prozentwert** |
   | 4 | A: `/workspaces/<id>/consent`, einen Scope widerrufen | B sieht die betroffenen Inhalte nicht mehr; der Event-Log hat einen Eintrag |
   | 5 | A: den Scope wieder erteilen | Zugriff ist wieder da (dieselbe Grant-Zeile) |
   | 6 | B: Shared Reflection anlegen | A sieht sie |
   | 7 | A: Dynamics, Relationship-Analyse starten | Job `QUEUED → GENERATING → COMPLETE` in < 5 min (bei `disabled` sichtbar `FAILED`, siehe G6) |
   | 8 | A: Einladung mit Methode **E-Mail** an eine Drittadresse, dann mit Konto B einlösen | **abgelehnt** (Gate G3) |
   | 9 | Optional: Workspace auflösen | Historie bleibt, künftiger Zugriff ist weg (ADR 013). Nur ausführen, wenn A und B das wollen |

6. Monitoring-Abfragen (read-only):
   ```bash
   $DC exec -T postgres psql -U numra -d numra -A -c "
     select 'invitations_pending', count(*) from connection_invitations where state='PENDING'
     union all select 'connections_active', count(*) from user_connections where status='ACTIVE'
     union all select 'workspaces_active', count(*) from relationship_workspaces where status='ACTIVE'
     union all select 'analysis_queued_gt_15min', count(*) from analysis_jobs
       where status='QUEUED' and created_at < now() - interval '15 minutes'
     union all select 'analysis_failed_24h', count(*) from analysis_jobs
       where status='FAILED' and updated_at > now() - interval '24 hours';"
   ```
7. **Abbruchkriterien, bei denen sofort Rollback (§8) erfolgt:**
   - jeder Hinweis auf Fremdzugriff (IDOR) oder Consent-Umgehung
   - `analysis_queued_gt_15min > 0` über zwei Healthcheck-Läufe
   - mehr als 3 neue `FAILED`-Analysejobs pro Tag ohne erklärte Ursache
   - 5xx-Rate der api > 1 % über 1 h
8. Execution-State: `V2_STAGE=2`, Abnahmeprotokoll mit Schritt 1–8 und Ergebnis.

## 8. Rollback (jede Stufe, < 2 Minuten)

```bash
sudo cp -p /etc/numra/numra.env "/etc/numra/numra.env.bak.$(date +%Y%m%dT%H%M%S)"
# betroffene Flags auf false setzen (bzw. die Zeilen entfernen, dann gilt der Default false)
$DC up -d --no-deps --force-recreate api
scripts/ops/v2-flag-probe.sh https://avenyth.de/api stage1   # bzw. stage0
```

- **Daten bleiben erhalten.** Connections, Workspaces, Consent und Analysen werden durch das Flag weder gelöscht noch aufgelöst. Beim Wieder-Einschalten ist der Zustand unverändert.
- Laufende Analyse-Jobs arbeitet der `analysis-worker` weiter ab, das ist unkritisch. Er kann weiterlaufen.
- Die UI zeigt `PhaseDisabledState`, keinen Fehler.
- Infrastruktur-Rollback (Stufe 0): Host-Compose aus `.bak` zurückkopieren, dann `$DC up -d --remove-orphans`.

## 9. Danach (nicht Teil dieses Runbooks)

| Nächste Stufe | Voraussetzung |
|---|---|
| `CHECKINS`, `TASKS` | Stufe 2 stabil ≥ 7 Tage |
| `EVIDENCE_LAYER` | Datenschutzerklärung um Life-Tracking ergänzt |
| `COPILOT` | KI-Hinweis im Copilot (A2), LLM-Call-Log (A7), asynchroner Copilot empfohlen (L08) |

## 10. Protokollvorlage für den Execution-State

```text
V2_STAGE=<0|1|2> · <Datum/Uhrzeit> · deployed_sha=<sha> · flags: v2=<>, connections=<>,
relationship_workspaces=<>, checkins=false, tasks=false, copilot=false, evidence=false ·
probe: RESULT OK (stage<N>) · llm_provider=<Klasse> · abnahme: <Schritte/Ergebnis> ·
rollback: nicht nötig | ausgeführt wegen <Grund>
```
