#!/usr/bin/env bash
# Harness fuer scripts/release/numra-drill.sh mit Docker-Attrappe (kein echter Docker-Zugriff).
# Belegt: Dry-Run erzeugt nichts, ein vollstaendiger Lauf bereinigt Container/Netzwerk/Arbeits-
# verzeichnis auch bei Fehlern, Passwoerter erscheinen nie in Prozessargumenten, Berichten oder
# der Ausgabe, prod ohne Schutzschalter wird verweigert.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRILL="${DRILL:-$SCRIPT_DIR/../numra-drill.sh}"
PASS_N=0
FAIL_N=0
ok() { PASS_N=$((PASS_N + 1)); printf 'ok   - %s\n' "$1"; }
bad() { FAIL_N=$((FAIL_N + 1)); printf 'FAIL - %s\n' "$1"; }
expect() { if [ "$2" -eq 0 ]; then ok "$1"; else bad "$1"; fi; }
b() { if "$@"; then echo 0; else echo 1; fi; }
only_image_inspect() { [ ! -e "$W/calls.log" ] || ! grep -qv '^docker image inspect' "$W/calls.log"; }
rc_is() { [ "$RC" -eq "$1" ]; }

new_world() {
  T=$(mktemp -d)
  BIN="$T/bin"
  W="$T/world"
  mkdir -p "$BIN" "$W" "$T/backups" "$T/reports" "$T/work"
  printf 'dump-data' > "$T/backups/numra-1.dump"
  (cd "$T/backups" && sha256sum numra-1.dump > numra-1.dump.sha256)
  touch -d '1 hour ago' "$T/backups/numra-1.dump"
  echo rev_old > "$W/alembic"
  cat > "$BIN/docker" <<'FAKE'
#!/usr/bin/env bash
W=$FAKE_WORLD
printf 'docker %s\n' "$*" >> "$W/calls.log"
case "$1" in
  image) [ -z "${FAKE_MISSING_IMAGE:-}" ] || exit 1 ;;
  network | rm) ;;
  run)
    for ((i = 1; i <= $#; i++)); do
      if [ "${!i}" = "--env-file" ]; then j=$((i + 1)); f="${!j}"; grep -h 'PASSWORD' "$f" >> "$W/pw" || true; fi
    done
    if [[ "$*" == *"alembic upgrade head"* ]]; then
      [ -z "${FAKE_MIGRATE_FAIL:-}" ] || exit 1
      echo rev_new > "$W/alembic"
    fi ;;
  exec)
    if [[ "$*" == *pg_restore* ]]; then cat > /dev/null
    elif [[ "$*" == *psql* ]]; then cat "$W/alembic"
    elif [ "${!#}" = "-" ]; then
      cat > /dev/null
      echo "PROBE ready 200 200 PASS"
      if [ -n "${FAKE_PROBE_FAIL:-}" ]; then echo "PROBE login 500 200 FAIL"; exit 1; fi
      echo "PROBE login_after_delete 401 401 PASS"
    fi ;;
esac
FAKE
  printf '#!/usr/bin/env bash\nexec "$@"\n' > "$BIN/sudo"
  chmod +x "$BIN"/*
  cat > "$T/drill.env" <<CFG
CONFIG_TARGET=audit
BACKUP_DIR=$T/backups
BACKUP_GLOB='numra-*.dump'
BACKUP_MAX_AGE_S=93600
REPORT_DIR=$T/reports
DRILL_WORKDIR=$T/work
DRILL_PG_IMAGE=pg:test
DRILL_REDIS_IMAGE=redis:test
DRILL_OLD_API_IMAGE=api:old
DRILL_NEW_API_IMAGE=api:new
DRILL_MIGRATE_IMAGE=mig:new
SUDO_CMD=$BIN/sudo
CFG
  chmod 600 "$T/drill.env"
  export PATH="$BIN:$PATH" FAKE_WORLD="$W"
}

drill() { RC=0; OUT=$(bash "$DRILL" --config "$T/drill.env" "$@" 2>&1) || RC=$?; }
reports_json() { cat "$T"/reports/drill-audit-drill-*.json; }

t_refusals() {
  new_world
  drill --dry-run
  expect "ohne --target: Exit 2" $((RC == 2 ? 0 : 1))
  sed -i 's/^CONFIG_TARGET=audit/CONFIG_TARGET=prod/' "$T/drill.env"
  drill --target prod
  expect "prod ohne --i-am-sure-prod: Exit 2" $((RC == 2 ? 0 : 1))
  drill --target audit --dry-run
  expect "Konfig/Target-Mismatch: Exit 2" $((RC == 2 ? 0 : 1))
  expect "Verweigerung ruft Docker nicht auf" "$(b test ! -e "$W/calls.log")"
}

t_dry_run() {
  new_world
  drill --target audit --dry-run
  expect "dry-run: Exit 0" $((RC == 0 ? 0 : 1))
  expect "dry-run: nur 'docker image inspect', nichts anderes" "$(b only_image_inspect)"
  expect "dry-run: kein Arbeitsverzeichnis angelegt" "$(b test -z "$(ls -A "$T/work")")"
  FAKE_MISSING_IMAGE=1 drill --target audit --dry-run
  expect "dry-run: fehlendes Image -> Exit 1" $((RC == 1 ? 0 : 1))
}

t_full() {
  new_world
  drill --target audit
  expect "Lauf: Exit 0" $((RC == 0 ? 0 : 1))
  python3 - "$T/reports" <<'PY'
import glob, json, sys
r = json.load(open(glob.glob(sys.argv[1] + "/drill-audit-drill-*.json")[0]))
ev = {s["id"]: s["evidence"] for s in r["steps"]}
assert r["result"] == "PASS" and r["dry_run"] is False
assert "vorher=rev_old nachher=rev_new" in ev["migrate"], ev
assert "alter-code:ready" in ev and "neuer-code:ready" in ev, ev
PY
  expect "Bericht: alembic vorher/nachher und beide Sonden" $?
  expect "Cleanup: Container und Netzwerk entfernt" "$(b grep -q 'docker network rm' "$W/calls.log")"
  expect "Cleanup: Arbeitsverzeichnis entfernt" "$(b test -z "$(ls -A "$T/work")")"
  local pw leaks=0
  pw=$(sed 's/^POSTGRES_PASSWORD=//' "$W/pw" | head -n 1)
  [ -n "$pw" ] || bad "Passwort wurde nicht erfasst"
  grep -rqF "$pw" "$W/calls.log" "$T/reports" && leaks=1
  grep -qF "$pw" <<< "$OUT" && leaks=1
  expect "Passwort weder in docker-Argumenten noch in Bericht/Ausgabe" $leaks
  expect "Passwort wird per --env-file uebergeben" "$(b grep -q -- '--env-file' "$W/calls.log")"
}

t_failures() {
  new_world
  FAKE_MIGRATE_FAIL=1 drill --target audit
  expect "Migration schlaegt fehl -> Exit 1" $((RC == 1 ? 0 : 1))
  expect "Fehlerfall: trotzdem Cleanup" "$(b grep -q 'docker network rm' "$W/calls.log")"
  expect "Fehlerfall: Arbeitsverzeichnis entfernt" "$(b test -z "$(ls -A "$T/work")")"
  new_world
  FAKE_PROBE_FAIL=1 drill --target audit
  expect "Sonde meldet FAIL -> Exit 1" $((RC == 1 ? 0 : 1))
  expect "Sonde: Bericht FAIL" "$(b grep -q '"result": "FAIL"' "$T"/reports/drill-audit-drill-*.json)"
  new_world
  touch -d '3 days ago' "$T/backups/numra-1.dump"
  drill --target audit
  expect "Dump zu alt -> Exit 1 ohne Docker-Mutation" "$(b rc_is 1)"
  expect "Dump zu alt: nur Image-Pruefungen, kein Cleanup-/Mutationsaufruf" "$(b only_image_inspect)"
}

t_static() {
  bash -n "$DRILL"
  expect "statisch: bash -n" $?
  if grep -n '|| true' "$DRILL"; then false; else true; fi
  expect "statisch: kein '|| true'" $?
  grep -q '^set -euo pipefail' "$DRILL"
  expect "statisch: set -euo pipefail" $?
}

for t in t_refusals t_dry_run t_full t_failures t_static; do
  printf '# %s\n' "$t"
  "$t"
done
printf '\n%s bestanden, %s fehlgeschlagen\n' "$PASS_N" "$FAIL_N"
[ "$FAIL_N" -eq 0 ]
