# Release-Verifizierungs-Runbook (Production, HermesTrader)

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
  upgraden.
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

### 7. Abschluss-Gate

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
