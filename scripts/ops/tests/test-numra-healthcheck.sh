#!/usr/bin/env bash
# Mock-docker/curl harness for scripts/ops/numra-healthcheck.sh.
#
# Laeuft vollstaendig in einem Temp-Verzeichnis: Konfig, Statusfile und Backup-Verzeichnis
# werden per CONFIG_FILE/STATUS_FILE/BACKUP_DIR injiziert, `docker` und `curl` sind
# Attrappen. Der Test liest und schreibt weder /etc/numra noch /usr/local/bin; ein
# strace-Lauf am Ende belegt das (uebersprungen, wenn strace fehlt).
#
# Abgedeckt: A6 (stale QUEUED), Alarmsemantik pro Dienst (EXPECTED_DEPENDENCIES),
# Schwellwert N, Erholung, ungueltiges/fehlendes JSON, HTTP 503 mit Body, 24h-Zaehlung
# inkl. Analysefehler.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HEALTHCHECK="$SCRIPT_DIR/../numra-healthcheck.sh"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

FAKE_BIN="$WORK/bin"
STATE="$WORK/state/health-status.json"
mkdir -p "$FAKE_BIN" "$WORK/backups" "$WORK/state"

# `docker exec ... psql -c "<sql>"`: Ausgabe kommt aus $PSQL_OUTPUT_FILE, das SQL wird
# zur Inspektion mitgeschrieben.
cat > "$FAKE_BIN/docker" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" > "$DOCKER_ARGS_FILE"
cat "$PSQL_OUTPUT_FILE"
EOF

# `curl -s -m 10 -w '\n%{http_code}' <url>`: Exit-Code, Body und HTTP-Status sind
# datei-gesteuert. Ohne -f liefert curl den Body auch bei 503.
cat > "$FAKE_BIN/curl" <<'EOF'
#!/usr/bin/env bash
rc=$(cat "$CURL_RC_FILE")
[ "$rc" -eq 0 ] || exit "$rc"
cat "$CURL_BODY_FILE"
printf '\n%s' "$(cat "$CURL_CODE_FILE")"
EOF
chmod +x "$FAKE_BIN/docker" "$FAKE_BIN/curl"

export PATH="$FAKE_BIN:$PATH"
export PSQL_OUTPUT_FILE="$WORK/psql-output"
export DOCKER_ARGS_FILE="$WORK/docker-args"
export CURL_RC_FILE="$WORK/curl-rc"
export CURL_BODY_FILE="$WORK/curl-body"
export CURL_CODE_FILE="$WORK/curl-code"
touch "$WORK/backups/numra-fresh.dump"

export CONFIG_FILE="$WORK/healthcheck.env"
export STATUS_FILE="$STATE"
export BACKUP_DIR="$WORK/backups"

write_config() {
  cat > "$CONFIG_FILE" <<EOF
PROD_READY_URL="http://fake/ready"
PROD_DB_CONTAINER=fake-prod
AUDIT_READY_URL=
EXPECTED_DEPENDENCIES="database=required numerology_engine=required llm=optional-disabled pdf=required"
${1:-}
EOF
}

# body <overall> <database> <engine> <llm> <pdf>
body() {
  printf '{"status":"%s","database":"%s","numerology_engine":"%s","llm":"%s","pdf":"%s"}' "$@"
}
healthy_body() { body healthy healthy healthy disabled healthy; }

set_health() { printf '%s' "$2" > "$CURL_BODY_FILE"; printf '%s' "$1" > "$CURL_CODE_FILE"; echo 0 > "$CURL_RC_FILE"; }
set_jobs() { printf '%s\n' "$1" > "$PSQL_OUTPUT_FILE"; }

reset_state() {
  rm -f "$STATE"
  write_config "${1:-}"
  set_jobs "0 0 0 0"
  set_health 200 "$(healthy_body)"
}

OUT="$WORK/out"; ERR="$WORK/err"
run() {
  set +e
  bash "$HEALTHCHECK" > "$OUT" 2> "$ERR"
  RC=$?
  set -e
}

fail() {
  echo "FAIL [$LABEL]: $1" >&2
  echo "--- exit $RC ---" >&2; echo "--- stdout ---" >&2; cat "$OUT" >&2
  echo "--- stderr ---" >&2; cat "$ERR" >&2
  echo "--- status ---" >&2; cat "$STATE" >&2 2>/dev/null || true
  exit 1
}

PASSED=0
LABEL=""
# check <label> <expected-exit>: einen Lauf ausfuehren und den Exit-Code pruefen.
check() {
  LABEL="$1"
  run
  [ "$RC" -eq "$2" ] || fail "expected exit $2, got $RC"
  PASSED=$((PASSED + 1))
  echo "ok [$LABEL]"
}
st() { python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(eval(sys.argv[2]))' "$STATE" "$1"; }
expect_st() {
  local actual; actual=$(st "$1")
  [ "$actual" = "$2" ] || fail "status $1: expected '$2', got '$actual'"
}
expect_err() { grep -q -- "$1" "$ERR" || fail "stderr lacks '$1'"; }
expect_no_err() { [ ! -s "$ERR" ] || fail "stderr should be empty"; }
expect_out() { grep -q -- "$1" "$OUT" || fail "stdout lacks '$1'"; }

# ---- A6: stale QUEUED (bestehende Faelle) ----------------------------------------------
reset_state
set_jobs "0 0 0 0"; check "no stale queued jobs" 0
set_jobs "0 0 0 3"; check "stale queued jobs trip the alarm" 1
expect_st 'd["prod_stale_queued"]' 3
expect_err "stale_queued_job"

# ---- neue Jobfehler / 24h-Rueckfall --------------------------------------------------
reset_state
set_jobs "0 0 0 0"; check "baseline jobs" 0
set_jobs "1 0 1 0"; check "new failed job since previous run alarms" 1
expect_err "new_failed_job"
reset_state
set_jobs "0 2 2 0"; check "no previous measurement: 24h window falls back" 1
expect_err "failed_job(s)_in_24h"

# 24h-Zaehlung umfasst Report- UND Analysefehler.
check "24h SQL counts analysis failures too" 0
tr '\n' ' ' < "$DOCKER_ARGS_FILE" | grep -qE "analysis_jobs where status='FAILED'[[:space:]]+and updated_at > now\(\) - interval '24 hours'" \
  || fail "psql query does not count analysis_jobs failures in 24h"

# ---- 2c: Alarmsemantik ---------------------------------------------------------------
reset_state
check "optional-disabled llm reports disabled: no alarm" 0
expect_no_err
expect_st 'd["warnings"]' "[]"
expect_st 'd["failures"]' "[]"

reset_state
set_health 200 "$(body healthy healthy healthy disabled disabled)"
check "required pdf reports disabled: config deviation" 1
expect_err "config_deviation"; expect_err "pdf"

reset_state
set_health 200 "$(body healthy healthy healthy healthy healthy)"
check "optional-disabled llm reports healthy: config deviation" 1
expect_err "config_deviation"; expect_err "llm"

reset_state
set_health 200 "$(body healthy healthy healthy degraded healthy)"
check "optional-disabled llm reports degraded: deviation, not suppressed" 1
expect_err "config_deviation"

reset_state
set_health 200 "$(body healthy healthy healthy disabled degraded)"
check "degraded required dep: warning only" 0
expect_st 'd["warnings"]' "['prod:pdf_degraded']"
expect_st 'd["prod_fail_count_pdf"]' 0

# HTTP 503 mit Body wird ausgewertet (kein curl -f); einmaliger Fehler -> nur Warnung.
reset_state
set_health 503 "$(body unhealthy healthy healthy disabled unhealthy)"
check "503 body evaluated: single failure is a warning" 0
expect_st 'd["prod_pdf"]' unhealthy
expect_st 'd["prod_fail_count_pdf"]' 1
expect_st 'd["failures"]' "[]"
expect_out "WARN"

check "second failure still below N=3" 0
expect_st 'd["prod_fail_count_pdf"]' 2
check "third consecutive failure: alarm" 1
expect_st 'd["prod_fail_count_pdf"]' 3
expect_err "pdf_unhealthy_3x"

# Erholung: Zaehler 0 + Entwarnung, danach keine Entwarnung mehr.
set_health 200 "$(healthy_body)"
check "recovery" 0
expect_st 'd["prod_fail_count_pdf"]' 0
expect_st 'd["recoveries"]' "['prod:pdf_recovered']"
expect_out "RECOVERED"
check "after recovery nothing left to announce" 0
expect_st 'd["recoveries"]' "[]"

# Zaehler bleiben zwischen Laeufen erhalten, Erholung dazwischen setzt zurueck.
reset_state
set_health 503 "$(body unhealthy healthy healthy disabled unhealthy)"
check "run 1 of 2" 0
set_health 200 "$(healthy_body)"
check "recovered in between" 0
set_health 503 "$(body unhealthy healthy healthy disabled unhealthy)"
check "counter restarted at 1" 0
expect_st 'd["prod_fail_count_pdf"]' 1

# Schwellwert ist konfigurierbar.
reset_state "FAIL_THRESHOLD=2"
set_health 503 "$(body unhealthy healthy healthy disabled unhealthy)"
check "N=2: first failure warns" 0
check "N=2: second failure alarms" 1

# Health-Endpunkt selbst fehlerhaft: ungueltiges JSON, fehlendes JSON, nicht erreichbar.
reset_state
set_health 200 "<html>oops</html>"
check "invalid JSON counts as failure (1/3)" 0
expect_st 'd["prod_readiness"]' invalid_json
expect_st 'd["prod_fail_count_readiness"]' 1
check "invalid JSON (2/3)" 0
check "invalid JSON (3/3) alarms" 1
expect_err "readiness_failed_3x"

reset_state
set_health 200 '{"database":"healthy"}'
check "JSON without status field counts as failure" 0
expect_st 'd["prod_fail_count_readiness"]' 1

reset_state
set_health 503 ""
check "503 with empty body counts as failure" 0
expect_st 'd["prod_fail_count_readiness"]' 1

reset_state
echo 7 > "$CURL_RC_FILE"
check "unreachable endpoint (1/3)" 0
expect_st 'd["prod_readiness"]' unreachable
check "unreachable (2/3)" 0
check "unreachable (3/3) alarms" 1
set_health 200 "$(healthy_body)"
check "endpoint recovers" 0
expect_st 'd["prod_fail_count_readiness"]' 0
expect_st 'd["recoveries"]' "['prod:readiness_recovered']"

# ohne EXPECTED_DEPENDENCIES: nur der Gesamtstatus zaehlt (rueckwaertskompatibel).
reset_state
write_config "EXPECTED_DEPENDENCIES="
set_health 200 "$(body healthy healthy healthy disabled disabled)"
check "no expectations configured: disabled deps are ignored" 0

# ---- Isolation: kein Zugriff auf /etc/numra oder /usr/local/bin ------------------------
LABEL="isolation"
if command -v strace > /dev/null 2>&1 && strace -f -o /dev/null true 2> /dev/null; then
  reset_state
  strace -f -e trace=file -o "$WORK/strace.log" bash "$HEALTHCHECK" > /dev/null 2>&1 || true
  [ -s "$WORK/strace.log" ] || fail "strace log is empty"
  if grep -E '"/etc/numra|/usr/local/bin/numra|"/usr/local/bin[^"]*"[^)]*(O_WRONLY|O_RDWR|O_CREAT)' "$WORK/strace.log" > "$WORK/strace.hits"; then
    cat "$WORK/strace.hits" >&2
    fail "healthcheck touched /etc/numra or /usr/local/bin"
  fi
  PASSED=$((PASSED + 1))
  echo "ok [strace: no access to /etc/numra or /usr/local/bin]"
else
  echo "skip [strace unavailable: isolation proof skipped]"
fi

echo "all numra-healthcheck.sh tests passed ($PASSED checks)"
