# Release-Verifizierungs-Runbook (Production, HermesTrader)

> **Host note (2026-09-19):** Production now runs on this host (`agent0-1`,
> `https://agent0-1.taile6801f.ts.net:8443`, deployment checkout `/opt/numra/repo`).
> The HermesTrader VPS still runs its stack as the explicit fallback until the
> operator approves retirement. This runbook was written for and executed against
> HermesTrader; its steps and rules apply unchanged to whichever host is primary —
> only the SSH target and the deployed paths differ (see
> `docs/ops/2026-09-19-hermestrader-to-agent0-migration.md`). Re-verify which host
> is primary before executing it, and never assume an auto-deploy timer exists on
> agent0: production there advances only by an explicit deploy.

## Zweck

Nach jedem Release, das `main` verändert (RBAC/Rollen, Migrationen, neue
`/v1/*`-Endpunkte o. ä.), verifiziert dieses Runbook auf dem Production-VPS
(HermesTrader), bevor irgendein manueller Eingriff (Redeploy, Migration,
Account-Änderung) erfolgt:

1. dass der auf `main` gemergte Commit tatsächlich deployed ist (nicht nur
   `git pull`-fähig, sondern real laufend),
2. dass die zugehörige Datenbank-Migration angewendet ist,
3. dass sicherheitsrelevante Änderungen (hier: Rollen/RBAC) sich production-seitig
   so verhalten wie in der CI getestet.

**Dieses Runbook beschreibt einen tatsächlich ausgeführten und erfolgreich
verifizierten Prozess** — nicht einen theoretisch angenommenen. Es wurde erstmals
für V1.6 Release A ("RBAC + Admin-Backend", PR #9,
`740923b9ad5f7b8a5cd2c958180e451be3da2d19`, Migration `cd916a8c6edd`) auf
HermesTrader ausgeführt und lieferte `RELEASE_A_PRODUCTION_VERIFIED`.

Es kann nur mit echtem SSH-Zugriff auf HermesTrader ausgeführt werden — nicht aus
einer Claude-Code-Cloud/Remote-Session, die keinen Netzwerkpfad zum VPS hat.

## Nicht verhandelbare Regeln

- **Kein automatisches `alembic upgrade head`.** Nur `alembic heads`/
  `alembic current` auswerten. Bei Abweichung stoppen und klären, nicht selbst
  upgraden. (Gilt für dieses Verifikations-Runbook; ein geplanter Release mit
  ausdrücklicher, freigegebener Migration folgt dem Abschnitt „Produktionsauslieferung:
  Ablauf, Marker, Rollback“.)
- **Kein Redeploy auf Verdacht.** Schlägt das SHA-Gate fehl: Auto-Updater-Logs
  prüfen, nicht selbst redeployen.
- **Kein Klartext-Passwort** in Kommandozeile, Shell-History, Prozessliste oder
  Log-Ausgabe. Zugangsdaten für API-Tests aus einer bestehenden geschützten
  Datei lesen, nie ausgeben.
- **Kein künstlicher Test-Account in Production**, nur um einen negativen
  RBAC-Test durchzuführen — existiert kein zweiter Nutzer, wird der Test als
  `NOT_RUN_NO_USER_ACCOUNT` protokolliert (der Fall ist bereits durch die
  Release-CI abgedeckt).
- Production-Compose immer explizit über `-p <projekt> --env-file <env> -f
  <compose-datei>` ansprechen, nie implizit über das aktuelle Arbeitsverzeichnis.

## Ablauf

### 1. Release-State-Gate (maschinenprüfbar, drei Werte)

```bash
set -Eeuo pipefail
EXPECTED_SHA="<commit-sha des zu verifizierenden Merges>"

cd /opt/numra/repo
git fetch origin --quiet
ORIGIN_MAIN="$(git rev-parse origin/main)"
REPO_HEAD="$(git rev-parse HEAD)"
DEPLOYED_SHA="$(cat /var/lib/numra/deployed_sha)"

printf 'EXPECTED_SHA=%s\nORIGIN_MAIN=%s\nREPO_HEAD=%s\nDEPLOYED_SHA=%s\n' \
  "$EXPECTED_SHA" "$ORIGIN_MAIN" "$REPO_HEAD" "$DEPLOYED_SHA"

[ "$ORIGIN_MAIN" = "$EXPECTED_SHA" ]  || { echo "FAIL: origin/main changed"; exit 20; }
[ "$REPO_HEAD" = "$EXPECTED_SHA" ]    || { echo "FAIL: host repo not on release"; exit 21; }
[ "$DEPLOYED_SHA" = "$EXPECTED_SHA" ] || { echo "FAIL: release not deployed"; exit 22; }
echo "PASS: ORIGIN_MAIN = REPO_HEAD = DEPLOYED_SHA = EXPECTED_SHA"
```

`deployed_sha` (`/var/lib/numra/deployed_sha`) ist die maßgebliche Deployment-
Wahrheit — nicht der Host-Repo-Checkout allein, da ein `git checkout` erfolgreich
sein kann, während Migration/Build danach fehlschlagen und die App noch die alte
Version ausführt.

### 2. Migration (zweite, getrennte Gleichheit)

```bash
DC="docker compose -p numra-prod \
  --env-file /etc/numra/numra.env \
  -f /opt/numra/compose.production.yml"

$DC ps -a
$DC run --rm migrate alembic heads
$DC run --rm migrate alembic current
# Ziel: current == heads == <erwartete Revision>
```

Hinweis zu Migrationen mit Tabellen-Locks (z. B. `c5a9d3e72b16`, setzt
`SET LOCAL lock_timeout = '5s'`): Worker und `analysis-worker` vor `alembic upgrade`
stoppen, damit keine offene Job-Transaktion die Zeile/Tabelle hält. Bei einem
Lock-Konflikt bricht die Migration kontrolliert ab (transaktional, nichts halb
angewendet); nach Beheben der Ursache einfach erneut ausführen.

### 3. Optionaler DB-Aggregat-Check (kein PII)

```bash
$DC exec -T postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "SELECT role, is_active, count(*) FROM users GROUP BY role, is_active ORDER BY role, is_active;"'
```

Liest DB-Name/User aus der Container-Umgebung statt sie hart zu verdrahten;
`POSTGRES_PASSWORD` wird nie ausgegeben oder als Shell-Argument herumgereicht.

### 4. Nur bei PASS in 1+2: Account-/Rollen-Änderung anwenden

```bash
$DC exec -T api python -m numra_api.cli admin list   # zeigt nur bestehende ADMINs
$DC exec -T api python -m numra_api.cli admin promote-admin --email '<owner-email>'
$DC exec -T api python -m numra_api.cli admin list
```

Idempotent — legt nie einen User an, ändert nie das Passwort; bereits-ADMIN ist
ein sauberer No-op.

### 5. API-Verifikation (vom lokalen Rechner, nie mit Klartext-Passwort in der CLI)

```text
1. Login (Admin) → 200, Session-Cookie
2. GET /api/v1/auth/me → role="ADMIN", is_active=true
3. GET /api/v1/admin/stats → 200
4. GET /api/v1/admin/users → 200
```

### 6. Negativer RBAC-Test

```text
Existiert ein regulärer USER-Account?
  Ja  → einloggen, GET /api/v1/admin/stats → erwartet 403
  Nein → NOT_RUN_NO_USER_ACCOUNT protokollieren (Fall bereits in Release-CI
         abgedeckt); realer Production-Nachweis folgt mit dem ersten regulär
         registrierten USER.
```

### 7. CORS-/Origin-Allowlist gegen den echten Web-Proxy prüfen (#187)

Der Web-Proxy reicht den `Origin`-Header des Browsers an die API durch.
`OriginValidationMiddleware` prüft ihn für state-ändernde Requests gegen
`CORS_ALLOWED_ORIGINS`. Steht die Origin, unter der das Deployment tatsächlich
erreichbar ist, dort nicht, schlägt **nur** der Weg über die Oberfläche fehl (403
`ORIGIN_NOT_ALLOWED`), während der Direktaufruf der API weiter funktioniert.

```bash
BASE="https://<produktions-host>:8443"
# Erwartet: 401 INVALID_CREDENTIALS (Guard passiert, Auth greift) -- NICHT 403.
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$BASE/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -H "Origin: $BASE" \
  -d '{"email":"origin-probe@example.com","password":"Not-A-Real-Password-123"}'
# Erwartet: 403 ORIGIN_NOT_ALLOWED -- der Guard muss auch abweisen.
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$BASE/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -H 'Origin: https://evil.example.org' \
  -d '{"email":"origin-probe@example.com","password":"Not-A-Real-Password-123"}'
```

Beide Zeilen gehören ins Abschluss-Gate. Ein 403 auf der ersten Zeile ist ein
Release-Blocker: die Oberfläche wäre für jeden Nutzer unbenutzbar.

### 8. Abschluss-Gate

Erst wenn jede Zeile PASS/erwarteter Wert zeigt, gilt `<RELEASE>_PRODUCTION_VERIFIED`:

```text
GitHub main / origin               PASS
Repo HEAD                          PASS
deployed_sha                       PASS
Alembic heads == current           PASS
Stack ($DC ps -a)                  HEALTHY
Account-/Rollen-Änderung           PASS
Positive API-Checks                200 / erwartete Felder
Negativer RBAC-Test                403 ODER NOT_RUN_NO_USER_ACCOUNT (+ CI-Beleg)
Kein Redeploy ausgelöst            YES
Kein Passwort geändert/rotiert     YES
Keine echten Nutzerdaten verändert YES
Kein Golden-Canon/Calculation-Code angefasst YES
```

## Verifizierte Ausführung: V1.6 Release A

- Ziel-Commit: `740923b9ad5f7b8a5cd2c958180e451be3da2d19` (PR #9)
- Ziel-Migration: `cd916a8c6edd` ("add user role status and audit log")
- Ergebnis: **`RELEASE_A_PRODUCTION_VERIFIED`** — Release-State-Gate PASS,
  Alembic `current == heads == cd916a8c6edd`, Stack HEALTHY, Owner-Promotion PASS
  (idempotenter No-op, Account war bereits ADMIN), `/auth/me` → `role=ADMIN`,
  `/admin/stats` und `/admin/users` → 200, negativer RBAC-Test
  `NOT_RUN_NO_USER_ACCOUNT` (zum Zeitpunkt der Prüfung existierte nur der eine
  Owner-Account; per DB-Aggregat-Check bestätigt: genau 1 Nutzer, `role=ADMIN`,
  `is_active=true`). Zusätzlich per String-Scan über die API-Antworten bestätigt:
  keine `password_hash`/`token_hash`/Secrets in `/auth/me`, `/admin/stats`,
  `/admin/users`, `/admin/audit`. `/admin/audit` zeigt genau einen
  `ADMIN_PROMOTED`-Eintrag (`actor_user_id: null`, `safe_metadata.promoted_via:
  "cli"`) aus der ursprünglichen Promotion — der erneute (No-op-)Aufruf erzeugte
  erwartungsgemäß keinen weiteren Eintrag. Kein Redeploy ausgelöst, kein Passwort
  geändert.

## Produktionsauslieferung: Ablauf, Marker, Rollback

Wiederverwendbare Vorlage für einen geplanten Produktionsrelease. Platzhalter:
`<S_ALT>` = bisheriger Produktionsstand (Checkout und Marker), `<S2>` = vollständige
Kandidaten-SHA, `<TS>` = Zeitstempel der Sicherung, `<ZIEL_REV>` = erwartete
Alembic-Revision nach dem Release, `<SCRATCH>` = temporäres Verzeichnis außerhalb des
Deployment-Checkouts. Konkrete Werte (SHAs, Hashes, Image-IDs, Zählerstände) gehören in
das Protokoll des jeweiligen Release, nicht in diese Vorlage.

`DC` ist wie in Schritt 2 definiert (`docker compose -p numra-prod --env-file
/etc/numra/numra.env -f /opt/numra/compose.production.yml`).

### Abgrenzung zu „Kein automatisches `alembic upgrade head`“

Die Regel oben gilt für das Verifikations-Runbook (Schritte 1 bis 8): Es prüft nur
(`alembic heads`/`alembic current`) und migriert nie selbst. Ein **geplanter Release**
ist etwas anderes: Die Migration ist dort ein ausdrücklicher, vorab freigegebener
Schritt mit festgelegter Ziel-Revision `<ZIEL_REV>` (Reihenfolge der Revisionen vorher
gegen den Compare `<S_ALT>`…`<S2>` geprüft), ausgeführt als `$DC run --rm migrate`
bei gestoppten Schreibern und mit Gleichheitsprüfung danach. Es gibt kein blindes
„upgrade auf Verdacht“. Nach dem Release dient das Verifikations-Runbook (Schritte 1
und 2) als unabhängige Gegenprobe.

### Grundsätze

- Host-Eingriffe seriell und durch genau eine Instanz.
- `alembic downgrade` wird **nicht** benutzt. Er kann Daten vernichten (z. B. gedropte
  Spalten); er ist nur ein Notfall (R3) nach ausdrücklicher Entscheidung.
- Rückwärtskompatibilität der Migrationen wird **vor** dem Release gezeigt: alter
  Code gegen die migrierte Datenbank (Drill auf einer Kopie), nicht angenommen. Nur
  was der Drill belegt, trägt Rollback-Stufe R1.
- Ein älteres Compose-Overlay oder ein Tag wie `pre-s1` ist **allein kein
  Rückrollnachweis**: Es sagt nichts darüber, welche Images tatsächlich liefen. Als
  Rückweg zählen nur die vor dem Build angelegten Rollback-Tags auf die laufenden
  Image-IDs (Release-Schritt 2.2) zusammen mit der gesicherten Compose-Datei, jeweils verifiziert.
- „Container läuft“ belegt nicht, dass der `analysis-worker` (oder `worker`) Jobs
  verarbeitet. Beleg ist ein Job im Zustand `COMPLETE` **und** eine zugehörige Zeile in
  `llm_generations` (Abnahme, Punkt „Worker-Pfad“).

### 1. Pre-Flight (lesend)

1. Drift-Check gegen die letzte Bestandsaufnahme: Checkout-HEAD und Marker
   `/var/lib/numra/deployed_sha` == `<S_ALT>`, sha256 der Host-Compose-Datei, Image-IDs
   aller laufenden Produktionscontainer, `alembic current`, Flag-Werte samt
   `updated_at`, Readiness, Zählstände (Nutzer, Analysen, Jobs). Abweichung: STOPP und
   klären.
2. Kandidat: `<S2>` == Audit-Abnahme-SHA == `origin/main`-HEAD zum Freeze; CI auf
   `<S2>` vollständig grün; Reviews vorhanden.
3. Backup-Gate: letzter Dump jünger als 26 h und sha256 geprüft; Restore-Drill der
   laufenden Woche bestanden.
4. Freigabe-Check: keine offenen Issues mit Label `uptime-alert`; ausreichend freier
   Plattenplatz (Richtwert 50 GB).

### 2. Sicherungen (vor jeder Änderung)

1. `sudo install -d -m 0700 /var/lib/numra/release-backups/<TS>`; dorthin sichern:
   `/opt/numra/compose.production.yml`, `/etc/numra/numra.env` (nur root lesbar,
   0600), systemd-Units und `/usr/local/bin/numra-*.sh`, die Marker-Dateien,
   `git rev-parse HEAD`, die Image-IDs aus `docker ps`, ein Dump der Tabelle
   `feature_flags`.
2. Rollback-Tags auf die **laufenden** Image-IDs setzen, nicht auf `:latest` (ein Tag
   kann von der laufenden ID abweichen): für jeden zu ersetzenden Dienst
   `docker tag <image-id> numra-prod-<dienst>:rollback-<TS>`. Prüfen: `docker image
   inspect` je Rollback-Tag == ID aus `docker inspect <container>`. Scheitert das
   Tagging per ID (containerd-Store), das Image per `docker save` sichern.
3. Dienste, die im Release unverändert bleiben (z. B. `pdf`), werden nicht neu gebaut
   oder neu gestartet.

### 3. Vorbereiten ohne Downtime

1. `git -C /opt/numra/repo fetch` und `git -C /opt/numra/repo checkout --detach <S2>`
   (Eigentümer des Checkouts beibehalten; fremde Untracked-Dateien unberührt lassen).
2. `diff` zwischen Repo-`deploy/compose.production.yml` bei `<S2>` und der Host-Datei:
   nur erwartete Unterschiede. Die neue Datei in `<SCRATCH>` mit `$DC config --quiet`
   (mit `-f <SCRATCH>/compose.production.yml`) validieren; die Host-Datei dabei **nicht**
   überschreiben.
3. Build mit der Scratch-Datei, niedrige Priorität: `nice -n 19 docker compose -p
   numra-prod --env-file /etc/numra/numra.env -f <SCRATCH>/compose.production.yml build
   <geänderte Dienste>`. Laufende Container bleiben unberührt. Build-Log sichern.
   Erfolg anhand der neuen Image-IDs prüfen, nicht mit `pgrep` auf den Build-Prozess
   warten.
4. Vorab-Prüfung „Welche Container würde Compose neu erzeugen?“: `$DC --dry-run up -d
   --no-deps api worker analysis-worker web` (globales Flag vor dem Unterbefehl; ab
   welcher Compose-Version verfügbar, ist vorab zu prüfen) und dieselbe Ausgabe ohne
   Dienstliste (`$DC --dry-run up -d`) vergleichen: Nur die geplanten Dienste dürfen
   „Recreate“ zeigen. Ohne `--dry-run`: `$DC config` und je Dienst die ID des
   laufenden Containers (`docker inspect -f '{{.Image}}' <container>`) mit der ID von
   `numra-prod-<dienst>:latest` vergleichen; ein Dienst mit abweichender ID würde bei
   einem `up -d` ohne Dienstliste neu erzeugt.

### 4. Wartungsfenster (Schreibpause)

1. Nutzer vorab informieren (kurze Fehler/Ausfall von Minuten); Fenster mit geringer
   Nutzung wählen.
2. Schreiber stoppen: `$DC stop web api worker analysis-worker`. Postgres, Redis und
   unveränderte Dienste laufen weiter.
3. Dump **während** der Pause: `sudo systemctl start numra-backup.service` (Host-
   Konfiguration unter `/etc/systemd/system`, nicht im Repository belegt; vorher
   prüfen, dass die Unit existiert); neuen Dump
   und sha256 prüfen, Größe plausibel (nicht kleiner als der letzte Dump ohne
   Erklärung). Dieser Dump ist die Basis für R2.
4. Neue Compose-Datei installieren: Sicherung liegt bereits in
   `release-backups/<TS>`; dann `sudo cp -p <SCRATCH>/compose.production.yml
   /opt/numra/compose.production.yml`.
5. Migration: `$DC run --rm migrate` mit Exit 0; danach `alembic current == heads ==
   <ZIEL_REV>` (Schritt 2 des Verifikations-Runbooks). Abbruch mittendrin: siehe
   „Migrationsabbruch“ unten.
6. Falls der Ziel-Stand einen `flags-init`-Job enthält: `$DC run --rm flags-init`
   (Exit 0, erwartet No-op bei bestehender Datenbank); danach Flag-Werte samt
   `updated_at` identisch zum Pre-Flight und keine neuen `FEATURE_FLAG_CHANGED`-Einträge
   in `admin_audit_events`.
7. Nach `run --rm migrate` und `run --rm flags-init` die Dienste **explizit** starten:
   `$DC up -d --no-deps api worker analysis-worker web`. Ein `$DC up -d` ohne
   Dienstliste erzeugt jeden Dienst neu, dessen Konfiguration oder Image von der
   Compose-Datei abweicht; das trifft z. B. `pdf`, wenn es auf einem Image läuft, das
   nicht mehr der aktuellen `:latest`-ID entspricht, obwohl es im Release unverändert
   bleiben soll. `--no-deps` verhindert zusätzlich, dass über `depends_on` weitere
   Dienste angefasst werden (Postgres/Redis laufen, `migrate`/`flags-init` sind schon
   gelaufen). Auf `healthy` warten, Zeitlimit 5 min.

### 5. Abnahme (minimal, mit synthetischem Konto)

Nur synthetisches Konto (`prod-smoke-<zufall>@example.com`), keine echten Nutzerdaten.
Vorher belegen, dass die Registrierung keine E-Mail auslöst. Am Ende
`POST /v1/account/delete-all` (204); Login danach 401.

- Readiness 200/healthy.
- Register, Login, `me`, `sessions`.
- CSRF: mutierender Request ohne Token → 403.
- Zugriffsschutz: Admin-Route als normaler Nutzer → 403; fremde oder nicht
  existierende Workspace-IDs → 404.
- Flag-Verhalten: ein ausgeschaltetes Feature liefert 503 `V2_PHASE_DISABLED`.
- Origin-Guard wie Schritt 7 oben (fremde Origin 403 `ORIGIN_NOT_ALLOWED`, eigene
  Origin nicht 403); Proxy-Weiterleitung von Set-Cookie/CSRF über die öffentliche URL.
- **Worker-Pfad (Pflicht):** Profil anlegen → Report-Job → Worker verarbeitet → Job
  `COMPLETE` → PDF-Export lesbar (Textextraktion) → `llm_generations`-Zeile mit
  `source='report'` und gefüllten Tokens. Ein laufender Container ersetzt diesen
  Beleg nicht. (Echter LLM-Aufruf, geringe Kosten.) Tokenfelder sind `NULL` (nie 0),
  wenn die Provider-Antwort keine `prompt_eval_count`/`eval_count` enthält; dann zählt
  `latency_ms` als Beleg, und die fehlenden Tokens sind im Abnahmebericht zu vermerken.
- Queue/Fehler: keine `QUEUED`-Jobs älter als 2 min, Zähler fehlgeschlagener Jobs
  unverändert, Health-JSON unauffällig.
- Pfade, die verifizierte Konten mit echtem Mailversand brauchen (z. B. Einladungen,
  Consent), werden nicht in Produktion getestet; sie sind Gegenstand der
  Audit-Abnahme auf identischer SHA. In Produktion nur als Zugriffsschutz (404/403).
- Aufräumen: Smoke-Konto samt Daten löschen; Nutzerzahl == Pre-Flight.

### 6. Marker (nur nach bestandener Abnahme, atomar)

```bash
printf '%s\n' "<S2>" | sudo tee /var/lib/numra/deployed_sha.new >/dev/null \
  && sudo chown --reference=/var/lib/numra/deployed_sha /var/lib/numra/deployed_sha.new \
  && sudo chmod --reference=/var/lib/numra/deployed_sha /var/lib/numra/deployed_sha.new \
  && sudo mv -f /var/lib/numra/deployed_sha.new /var/lib/numra/deployed_sha
```

Der Marker wird erst nach vollständig bestandener Abnahme geschrieben und per
`mv` im selben Verzeichnis ersetzt (kein halb geschriebener Marker). `sudo tee` legt die
Datei als root an; `chown`/`chmod --reference` übernehmen Eigentümer und Rechte der
bisherigen Marker-Datei. Ein abgebrochener oder zurückgerollter Versuch hinterlässt **keinen**
Erfolgsmarker: der Marker bleibt `<S_ALT>`.

### 7. Abbruchkriterien

- Migration Exit ≠ 0 oder `alembic current` ≠ `<ZIEL_REV>`: STOPP, Dienste **nicht**
  mit den neuen Images starten; weiter nach „Migrationsabbruch“ unten.
- `flags-init` ist kein No-op, oder Flag-Werte/`updated_at` haben sich geändert: STOPP.
- Readiness nicht 200/healthy 5 min nach dem Start; `api` oder `worker` im
  Restart-Loop; Log-Fehler mit `column`, `relation` oder `Traceback`.
- Fehler bei Login, CSRF, Zugriffsschutz, Worker-Pfad, Report oder PDF in der Abnahme.
- Aktion: R1 ausführen, Ergebnis kontrollieren (Readiness, Login, Image-ID der
  laufenden Container == ID des Rollback-Tags, nach R1 (a) und (c) erfüllbar), Marker
  unverändert lassen, Bericht schreiben.

#### Migrationsabbruch

Befund im Repository (Stand `main` bei der Erstellung): `apps/api/alembic/env.py` setzt
`transaction_per_migration` nirgends (kein Treffer im Verzeichnis `apps/api`) und
führt `context.run_migrations()` in genau einem `with context.begin_transaction():`
aus (`env.py:48-49`, offline `env.py:41-42`); Alembic schreibt die Versionstabelle
dabei in derselben Transaktion fort. `_record_starting_heads()` (`env.py:24-29,47`)
liest nur die Startrevisionen und committet nichts. In den Migrationen unter
`apps/api/alembic/versions/` gibt es keinen `autocommit_block`, kein `CONCURRENTLY`
und kein explizites `commit`. Mit PostgreSQL (transaktionales DDL) gilt damit für
alle in einem Lauf anstehenden Revisionen (z. B. eine Kette über mehrere Revisionen)
alles oder nichts: Scheitert eine Revision, wird die gesamte Kette zurückgerollt und
`alembic current` bleibt auf der Startrevision. Das ist aus dem Code abgeleitet, nicht
durch einen Fehlerabbruch-Drill belegt; bei jedem Ziel-Stand `<S2>` erneut prüfen
(Migrationen mit `autocommit_block`/`CONCURRENTLY` heben diese Aussage auf).

- **`alembic current` unverändert (Startrevision):** Datenbank unverändert. Dienste
  mit den Rollback-Tags starten (R1), Ursache beheben, danach `$DC run --rm migrate`
  erneut. Das ist der erwartete Fall.
- **`alembic current` auf einer Zwischenrevision** (nach obigem Befund nicht zu
  erwarten, z. B. bei manuellem Eingriff oder abweichender Migration): nicht
  blind erneut `upgrade` ausführen. Sicherer Weg ist R2, der Restore des in der
  Schreibpause gezogenen Dumps (Schritt 4.3). Erneutes `upgrade` nur, wenn jede
  Revision bis zur Zielrevision als wiederholbar geprüft ist.
- Stand des Nachweises: Gezeigt wurde bisher der Weg Dump → Migration bis zur
  Ziel-Revision. Ein Fehlerabbruch mitten in der Migration (und der Restore danach)
  wurde **nicht** geübt.

### 8. Rollback-Stufen

| Stufe | Wann | Vorgehen |
|---|---|---|
| R1 Code-Rollback (bevorzugt) | Fehler im neuen Code, Daten intakt | Schritte (a) bis (d) unten; Marker nicht ändern. Die Datenbank bleibt auf `<ZIEL_REV>`; das trägt nur, wenn der Vorab-Drill (alter Code gegen migrierte DB) bestanden war. Richtwert 2 bis 5 min. |
| R2 Datenrestore | nur bei Datenkorruption | Schreiber stoppen, `pg_restore` aus dem Dump der Schreibpause (4.3). Daten nach dem Wiederanlauf gehen verloren; daher nur vor Freigabe des Zugangs oder mit ausdrücklicher Verlust-Entscheidung. |
| R3 Notfall | nur nach ausdrücklicher Freigabe | `alembic downgrade`. Nicht Teil des Regelwegs (Datenverlust möglich). |

#### R1 im Detail

`deploy/compose.production.yml` definiert für die selbst gebauten Dienste nur
`build:`, keine `image:`-Namen. Compose verwendet daher `numra-prod-<dienst>:latest`;
ein `up -d --no-build` startet nach dem Build die **neuen** Images, auch wenn
`rollback-<TS>`-Tags existieren. Die Tags wirken erst, wenn `:latest` zurückgesetzt ist.

a. Optional die neuen Images zur Analyse sichern: `docker tag numra-prod-<dienst>:latest
   numra-prod-<dienst>:failed-<TS>`. Dann `:latest` zurücksetzen, für jeden Dienst der
   alten Compose-Datei (`api`, `web`, `worker`, `analysis-worker`, `migrate`):
   `docker tag numra-prod-<dienst>:rollback-<TS> numra-prod-<dienst>:latest`.
b. Die alte Compose-Datei aus `/var/lib/numra/release-backups/<TS>/compose.production.yml`
   mit `-f` verwenden (`DC_ALT` = `DC` mit diesem `-f`) und danach mit `sudo cp -p`
   auf `/opt/numra/compose.production.yml` zurückkopieren, damit die Host-Datei zum
   laufenden Stand passt.
c. Explizit starten: `$DC_ALT up -d --no-build --no-deps api worker analysis-worker web`.
   Keine Dienstliste ohne `--no-deps`, damit `pdf`, Postgres und Redis unberührt
   bleiben.
d. Prüfen, je Dienst: ID des laufenden Containers (`docker inspect -f '{{.Image}}'
   $($DC_ALT ps -q <dienst>)`) == ID des Rollback-Tags (`docker image inspect -f
   '{{.Id}}' numra-prod-<dienst>:rollback-<TS>`). Diese Gleichheit ist erst nach (a)
   und (c) erfüllbar; vorher zeigt sie die neuen Images.

Nach jedem Rollback: Readiness, Image-IDs gemäß (d), Login, Marker unverändert
`<S_ALT>`.

### 9. Nach dem Wechsel

- Host-Healthcheck-Skript auf den neuen Stand prüfen, Timer-Lauf beobachten; 24 h
  beobachten (Readiness, Jobfehler, Backup-Frische, `uptime-alert`-Issues).
- Statuskopf in `docs/planning/avenyth-pwa-execution-state.md` aktualisieren
  (Repository-, Audit-, Produktions-Stand, Messzeitpunkt, Belege).
- Abhängigkeiten des Release dokumentieren, die Nutzer betreffen (z. B. Konten, die
  erst nach E-Mail-Verifizierung einladen können).


## Betriebsentscheidung: `GET /v1/health/ready` bleibt DB-hart (2026-09-24)

`_overall_status()` in `apps/api/src/numra_api/routes/health.py` entscheidet
Readiness ausschließlich über den Datenbank-Check; `numerology_engine`, `llm` und
`pdf` werden weiterhin einzeln geprüft und im Payload zurückgegeben, fließen aber
**nicht** in `status` ein.

Diese Entscheidung ist bewusst (nicht nur für `llm`/`pdf`, sondern ausdrücklich
auch für `numerology_engine`):

- Der Engine-Check ist ein reiner In-Process-Funktionsaufruf (`calculate_profile`
  gegen ein festes Probe-Profil) ohne externe Abhängigkeit. Fällt er, ist der
  Python-Prozess selbst in einem inkonsistenten Zustand — ein Readiness-Flip würde
  den Pod aus dem Traffic nehmen, aber das eigentliche Problem (ein kaputter
  Prozess) nicht beheben; ein Neustart des Pods hilft hier mehr als ein
  NotReady-Zustand.
  Verhaltensänderung: keine — dies ist eine reine Klarstellung, kein Code-Fix.
- Sollte Readiness später bewusst als "Canon-Engine ist importierbar und
  rechenfähig" neu definiert werden (z. B. weil ein separater Health-Check-Prozess
  ohne die Engine denkbar wird), gehört das in einen eigenen PR mit eigenem Eintrag
  hier — nicht rückwirkend in diesen.

Statuscode: `GET /v1/health/ready` liefert nur dann HTTP 503, wenn die Datenbank
`unhealthy` ist; `unhealthy` bei `llm`/`pdf`/`numerology_engine` sowie `degraded`/`disabled`
ändern den Statuscode nicht (200). Der Body bleibt in beiden Fällen vollständig.
