#!/usr/bin/env bash
# Harness fuer scripts/release/numra-release.sh mit Attrappen fuer docker, git, curl, sudo,
# systemctl, df und nice. Alle Pfade liegen in einem Temp-Verzeichnis; der Test beruehrt weder
# Docker noch /etc, /opt oder /var. Jeder mutierende Aufruf (docker tag/compose stop|up|run|build,
# git fetch/checkout, sudo install|cp|mv|tee|chown|chmod, systemctl) wird in $MUT_LOG
# protokolliert; ein Dry-Run-Test schlaegt fehl, sobald dort etwas steht oder sich das
# Dateisystem ausserhalb von REPORT_DIR aendert. Ein Mutationstest belegt, dass der Detektor
# eine kaputte Dry-Run-Absicherung tatsaechlich erkennt.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELEASE="${RELEASE:-$SCRIPT_DIR/../numra-release.sh}"
REPORT_PY="$SCRIPT_DIR/../../ops_report/report.py"
SENTINEL="s3cr3t-sentinel-$$-do-not-leak"
OLD=1111111111111111111111111111111111111111
NEW=2222222222222222222222222222222222222222
REV_OLD=rev_old
REV_NEW=rev_new
PASS_N=0
FAIL_N=0

ok() { PASS_N=$((PASS_N + 1)); printf 'ok   - %s\n' "$1"; }
bad() { FAIL_N=$((FAIL_N + 1)); printf 'FAIL - %s\n' "$1"; }
expect() { # expect "name" cond-exit-status
  if [ "$2" -eq 0 ]; then ok "$1"; else bad "$1"; fi
}

b() { if "$@"; then echo 0; else echo 1; fi; }
log_empty() { [ ! -s "$MUT_LOG" ]; }
log_nonempty() { [ -s "$MUT_LOG" ]; }
marker_is() { [ "$(cat "$T/marker")" = "$1" ]; }
head_is() { [ "$(cat "$W/head")" = "$1" ]; }
rc_marker() { [ "$RC" -eq "$1" ] && marker_is "$2"; }
rc_head() { [ "$RC" -eq "$1" ] && head_is "$2"; }
marker_atomic() { grep -q "mv -f $T/marker.new $T/marker" "$MUT_LOG" && [ ! -e "$T/marker.new" ]; }

new_world() {
  T=$(mktemp -d)
  W="$T/world"; BIN="$T/bin"; MUT_LOG="$T/mutations.log"; REPORTS="$T/reports"
  mkdir -p "$W/containers" "$W/tags" "$BIN" "$T/backups" "$T/state" "$T/rb" "$T/repo" "$REPORTS"
  : > "$MUT_LOG"
  local svc
  for svc in api web worker analysis-worker; do
    echo "sha256:old-$svc" > "$W/containers/numra-test-$svc-1.image"
    echo "t0" > "$W/containers/numra-test-$svc-1.started"
    echo "sha256:old-$svc" > "$W/tags/numra-test-${svc}_latest"
  done
  for svc in postgres redis pdf; do
    echo "sha256:fixed-$svc" > "$W/containers/numra-test-$svc-1.image"
    echo "t0" > "$W/containers/numra-test-$svc-1.started"
  done
  echo "sha256:old-migrate" > "$W/tags/numra-test-migrate_latest"
  echo "$REV_OLD" > "$W/alembic"
  echo "inv-1" > "$W/invariant"
  echo "$OLD" > "$W/head"
  echo 200 > "$W/ready"
  echo "services:" > "$T/compose.yml"
  printf 'services:\n  api: {}\n' > "$W/compose.new"
  echo "SECRET_VALUE=$SENTINEL" > "$T/numra.env"
  echo "$OLD" > "$T/marker"
  printf 'dump' > "$T/backups/numra-1.dump"
  (cd "$T/backups" && sha256sum numra-1.dump > numra-1.dump.sha256)
  touch -d '1 hour ago' "$T/backups/numra-1.dump"
  make_fakes
  cat > "$T/release.env" <<EOF
CONFIG_TARGET=audit
PROJECT=numra-test
COMPOSE_FILE=$T/compose.yml
ENV_FILE=$T/numra.env
REPO_DIR=$T/repo
COMPOSE_SRC_IN_REPO=deploy/compose.yml
WRITER_SERVICES="api web worker analysis-worker"
UNTOUCHED_SERVICES="postgres redis pdf"
MIGRATE_SERVICE=migrate
IMAGE_PREFIX=numra-test-
PG_SERVICE=postgres
DB_USER=numra
DB_NAME=numra
INVARIANT_SQL="select md5(x) from t"
READY_URL=http://127.0.0.1:1/ready
MARKER_FILE=$T/marker
STATE_DIR=$T/state
REPORT_DIR=$REPORTS
BACKUP_DIR=$T/backups
BACKUP_GLOB='numra-*.dump'
BACKUP_MAX_AGE_S=93600
FRESH_DUMP_MAX_AGE_S=300
RELEASE_BACKUP_ROOT=$T/rb
BACKUP_FILES="$T/numra.env"
BACKUP_SERVICE=numra-backup.service
HEALTH_TIMER=numra-health.timer
MIN_FREE_GB=50
DISK_PATH=/
SUDO_CMD=$BIN/sudo
HEALTHY_WAIT_ROUNDS=2
HEALTHY_WAIT_S=0
EOF
  export PATH="$BIN:$PATH" FAKE_WORLD="$W" MUT_LOG PGPASSWORD="$SENTINEL"
}

make_fakes() {
  cat > "$BIN/docker" <<'EOF'
#!/usr/bin/env bash
# Attrappe: protokolliert jeden Aufruf (Argumente) in $W/calls.log, mutierende zusaetzlich in $MUT_LOG.
W=$FAKE_WORLD
printf 'docker %s\n' "$*" >> "$W/calls.log"
mut() { printf 'docker %s\n' "$*" >> "$MUT_LOG"; }
case "$1" in
  ps)
    if [[ "$*" == *'{{.Status}}'* ]]; then
      for f in "$W"/containers/*.image; do echo "${FAKE_STATUS:-Up 1 minute (healthy)}"; done
    else
      for f in "$W"/containers/*.image; do basename "$f" .image; done
    fi ;;
  inspect)
    img=$(cat "$W/containers/$4.image")
    case "$3" in
      '{{.Image}}') echo "$img" ;;
      *) echo "$img $(cat "$W/containers/$4.started")" ;;
    esac ;;
  image)
    f="$W/tags/${3//[:\/]/_}"
    [ -f "$f" ] && cat "$f" || exit 1 ;;
  tag) mut "$@"; echo "$2" > "$W/tags/${3//[:\/]/_}" ;;
  logs) echo "ok"; [ -z "${FAKE_TRACEBACK:-}" ] || echo "Traceback (most recent call last)" ;;
  exec)
    sql="${!#}"
    case "$sql" in
      *alembic_version*) cat "$W/alembic" ;;
      *md5*) cat "$W/invariant" ;;
      select*) echo 1 ;;
      *) mut "$@" ;;
    esac ;;
  compose)
    shift
    while [ $# -gt 0 ]; do
      case "$1" in
        -p | --env-file | --project-directory | -f) shift 2 ;;
        *) break ;;
      esac
    done
    dry=0; [ "$1" != "--dry-run" ] || { dry=1; shift; }
    verb=$1; shift
    svcs=(); for a in "$@"; do case "$a" in -*) ;; *) svcs+=("$a") ;; esac; done
    case "$verb" in
      config) [ -z "${FAKE_COMPOSE_CONFIG_FAIL:-}" ] || exit 1 ;;
      up)
        if [ "$dry" = 1 ]; then
          for s in "${svcs[@]}"; do echo " Container numra-test-$s-1 Recreate"; done
          [ -z "${FAKE_DRYRUN_TOUCHES_PG:-}" ] || echo " Container numra-test-postgres-1 Recreate"
        else
          mut compose up "$@"
          for s in "${svcs[@]}"; do
            if [ -n "${FAKE_UP_WRONG_IMAGE:-}" ]; then echo "sha256:wrong" > "$W/containers/numra-test-$s-1.image"
            else cp "$W/tags/numra-test-${s}_latest" "$W/containers/numra-test-$s-1.image"; fi
            date +%s%N > "$W/containers/numra-test-$s-1.started"
          done
        fi ;;
      build)
        mut compose build "$@"
        for s in "${svcs[@]}"; do echo "sha256:new-$s" > "$W/tags/numra-test-${s}_latest"; done ;;
      stop) mut compose stop "$@" ;;
      run)
        mut compose run "$@"
        [ -z "${FAKE_MIGRATE_TO:-}" ] || echo "$FAKE_MIGRATE_TO" > "$W/alembic" ;;
    esac ;;
  *) echo "fake docker: unbekannt $*" >&2; exit 99 ;;
esac
EOF
  cat > "$BIN/git" <<'EOF'
#!/usr/bin/env bash
W=$FAKE_WORLD
printf 'git %s\n' "$*" >> "$W/calls.log"
[ "$1" = "-C" ] && shift 2
case "$1" in
  rev-parse) cat "$W/head" ;;
  fetch) printf 'git %s\n' "$*" >> "$MUT_LOG" ;;
  checkout) printf 'git %s\n' "$*" >> "$MUT_LOG"; echo "${!#}" > "$W/head" ;;
  show) cat "$W/compose.new" ;;
  *) echo "fake git: unbekannt $*" >&2; exit 99 ;;
esac
EOF
  cat > "$BIN/curl" <<'EOF'
#!/usr/bin/env bash
cat "$FAKE_WORLD/ready"
EOF
  cat > "$BIN/df" <<'EOF'
#!/usr/bin/env bash
printf 'Avail\n %sG\n' "${FAKE_FREE:-500}"
EOF
  cat > "$BIN/nice" <<'EOF'
#!/usr/bin/env bash
shift 2
exec "$@"
EOF
  cat > "$BIN/systemctl" <<'EOF'
#!/usr/bin/env bash
printf 'systemctl %s\n' "$*" >> "$MUT_LOG"
if [ "$1" = start ] && [ "$2" = numra-backup.service ]; then
  touch "$(dirname "$MUT_LOG")/backups/numra-1.dump"
fi
EOF
  cat > "$BIN/sudo" <<'EOF'
#!/usr/bin/env bash
case "$1" in install | cp | mv | tee | chown | chmod) printf 'sudo %s\n' "$*" >> "$MUT_LOG" ;; esac
exec "$@"
EOF
  chmod +x "$BIN"/*
}

snapshot_fs() { # Dateisystem-Zustand ausserhalb von REPORT_DIR (Inhalt + Metadaten)
  (cd "$T" && find . -path "./reports" -prune -o -path "./world/calls.log" -prune -o -path "./mutations.log" -prune \
    -o -type f -print0 | sort -z | xargs -0 sha256sum; find . -path "./reports" -prune -o -print | sort) | sha256sum
}

release() { # release ARGS... ; setzt RC und OUT
  RC=0
  OUT=$(bash "$RELEASE" --config "$T/release.env" "$@" 2>&1) || RC=$?
}
base_args() { echo "--target audit --old-sha $OLD"; }

phase() { # phase NAME [extra...]
  local p=$1; shift
  # shellcheck disable=SC2046
  release $(base_args) --new-sha "$NEW" --phase "$p" "$@"
}

full_to_switch() {
  phase baseline; [ "$RC" -eq 0 ] || return 1
  phase pre; [ "$RC" -eq 0 ] || return 1
  phase prep; [ "$RC" -eq 0 ] || return 1
  FAKE_MIGRATE_TO=$REV_NEW phase switch --expect-revision "$REV_NEW"
}

make_smoke() { # make_smoke FILE STATUS SHA [dry]
  printf 'PASS\tcheck\tok\n' > "$T/rec"
  [ "$2" != FAIL ] || printf 'FAIL\tcheck2\tkaputt\n' >> "$T/rec"
  local extra=()
  [ "${4:-}" != dry ] || extra=(--dry-run)
  python3 "$REPORT_PY" render --records "$T/rec" --out-dir "$T/smoke" --kind acceptance --target audit \
    --target-sha "$3" --script numra_acceptance.py --script-version t --started "$(date -u +%Y-%m-%dT%H:%M:%S+00:00)" \
    "${extra[@]}" > /dev/null || true
  cp "$T"/smoke/acceptance-audit-*.json "$1"
  rm -f "$T"/smoke/*
}

# ---------------------------------------------------------------- Tests

t_usage_refusals() {
  new_world
  release --config "$T/release.env" --phase pre --old-sha "$OLD" --new-sha "$NEW"
  expect "ohne --target: Exit 2 (kein Default)" $((RC == 2 ? 0 : 1))
  release --config "$T/release.env" --target staging --phase pre --old-sha "$OLD" --new-sha "$NEW"
  expect "ungueltiges --target: Exit 2" $((RC == 2 ? 0 : 1))
  release --target prod --config "$T/release.env" --phase pre --old-sha "$OLD" --new-sha "$NEW"
  expect "prod mit audit-Konfig: Exit 2 (CONFIG_TARGET passt nicht)" $((RC == 2 ? 0 : 1))
  sed -i 's/^CONFIG_TARGET=audit/CONFIG_TARGET=prod/' "$T/release.env"
  release --target prod --config "$T/release.env" --phase prep --old-sha "$OLD" --new-sha "$NEW"
  expect "prod prep ohne Schutzschalter: Exit 2" $((RC == 2 ? 0 : 1))
  release --target prod --config "$T/release.env" --phase prep --old-sha "$OLD" --new-sha "$NEW" --i-am-sure-prod --confirm-sha deadbeef
  expect "prod prep mit falschem --confirm-sha: Exit 2" $((RC == 2 ? 0 : 1))
  expect "Verweigerung mutiert nichts" $(b log_empty)
  release --target prod --config "$T/release.env" --phase switch --old-sha "$OLD" --new-sha "$NEW"
  expect "switch ohne --expect-revision: Exit 2" $((RC == 2 ? 0 : 1))
}

t_pre_report() {
  new_world
  phase baseline
  expect "baseline: Exit 0" $((RC == 0 ? 0 : 1))
  phase pre
  expect "pre: Exit 0" $((RC == 0 ? 0 : 1))
  local json
  json=$(ls "$REPORTS"/release-audit-pre-*.json)
  python3 - "$json" "$NEW" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
assert r["result"] == "PASS" and r["target"] == "audit" and r["target_sha"] == sys.argv[2]
assert r["script_version"] and r["started"] and r["finished"] and r["scope"] and r["limitations"]
ids = {s["id"] for s in r["steps"]}
assert {"backup-age", "backup-sha256", "alembic-before", "ready", "drift"} <= ids, ids
assert {s["status"] for s in r["steps"]} <= {"PASS", "FAIL", "SKIP", "INFO"}
PY
  expect "pre: JSON-Bericht mit Ziel-SHA, Version, Umfang, Einschraenkungen, Pruefungen" $?
  ls "$REPORTS"/release-audit-pre-*.md > /dev/null
  expect "pre: Markdown-Bericht vorhanden" $?
  grep -q "Einschraenkungen" "$REPORTS"/release-audit-pre-*.md
  expect "pre: Markdown nennt Einschraenkungen" $?
  expect "pre mutiert nichts" $(b log_empty)
}

t_pre_failures() {
  new_world; phase baseline
  touch -d '2 days ago' "$T/backups/numra-1.dump"
  phase pre
  expect "pre: zu altes Backup -> Exit 1" $((RC == 1 ? 0 : 1))
  grep -q '"result": "FAIL"' "$REPORTS"/release-audit-pre-*.json
  expect "pre: Bericht meldet FAIL" $?
  new_world; phase baseline
  echo "other_rev" > "$W/alembic"
  phase pre
  expect "pre: Drift (alembic != Baseline) -> Exit 1" $((RC == 1 ? 0 : 1))
  new_world; phase baseline
  echo "tampered" > "$T/backups/numra-1.dump"; touch -d '1 hour ago' "$T/backups/numra-1.dump"
  phase pre
  expect "pre: Dump-sha256 stimmt nicht -> Exit 1" $((RC == 1 ? 0 : 1))
  new_world; phase baseline
  echo "$NEW" > "$T/marker"
  phase pre
  expect "pre: Marker != old-sha -> Exit 1" $((RC == 1 ? 0 : 1))
  new_world; phase baseline
  FAKE_FREE=10 phase pre
  expect "pre: zu wenig Platz -> Exit 1" $((RC == 1 ? 0 : 1))
  new_world; phase baseline
  echo 503 > "$W/ready"
  phase pre
  expect "pre: Readiness 503 -> Exit 1" $((RC == 1 ? 0 : 1))
}

t_dry_run() {
  new_world
  phase baseline
  # baseline selbst ist ein Schreibvorgang (State-Datei); der Dry-Run beginnt danach.
  : > "$MUT_LOG"
  local snap_before snap_after p
  snap_before=$(snapshot_fs)
  for p in pre prep switch marker rollback; do
    phase "$p" --dry-run --expect-revision "$REV_NEW" --smoke-report "$T/none.json"
    expect "dry-run $p: Exit 0" $((RC == 0 ? 0 : 1))
  done
  expect "dry-run: kein mutierender docker/git/sudo/systemctl-Aufruf" $(b log_empty)
  snap_after=$(snapshot_fs)
  expect "dry-run: Dateisystem ausserhalb REPORT_DIR unveraendert" $(b test "$snap_before" = "$snap_after")
  grep -q '"dry_run": true' "$(ls "$REPORTS"/release-audit-prep-*.json | head -n 1)"
  expect "dry-run: Bericht ist als Dry-Run gekennzeichnet" $?
  # Negativkontrolle: derselbe Detektor schlaegt bei echter Mutation an
  : > "$MUT_LOG"
  phase prep
  expect "Negativkontrolle: echtes prep wird vom Mutationsprotokoll erfasst" $(b log_nonempty)
}

t_dry_run_detector_catches_broken_guard() {
  new_world
  phase baseline
  : > "$MUT_LOG"
  mkdir -p "$T/release"
  # Mutation: die Dry-Run-Absicherung in prep wird ausgehebelt
  awk '/^phase_prep\(\) \{/ { inprep = 1 }
    inprep && !done && /if \[ "\$DRY_RUN" = 1 \]; then/ { sub(/DRY_RUN" = 1/, "DRY_RUN\" = 99"); done = 1 }
    { print }' "$RELEASE" > "$T/release/numra-release.sh"
  cp -r "$SCRIPT_DIR/../../ops_report" "$T/ops_report"
  cmp -s "$RELEASE" "$T/release/numra-release.sh" && { bad "Mutationstest: Mutation wurde nicht angewendet"; return; }
  RC=0
  OUT=$(bash "$T/release/numra-release.sh" --config "$T/release.env" --target audit --old-sha "$OLD" --new-sha "$NEW" --phase prep --dry-run 2>&1) || RC=$?
  expect "Mutationstest: kaputte Dry-Run-Absicherung fuehrt zu Mutation (Detektor schlaegt an)" $(b log_nonempty)
}

t_full_cycle() {
  new_world
  full_to_switch
  expect "baseline->pre->prep->switch: Exit 0" $((RC == 0 ? 0 : 1))
  [ "$RC" -eq 0 ] || { echo "$OUT" | tail -n 15; }
  expect "switch: Marker noch NICHT gesetzt" $(b marker_is "$OLD")
  python3 - "$REPORTS" <<'PY'
import glob, json, sys
r = json.load(open(glob.glob(sys.argv[1] + "/release-audit-switch-*.json")[0]))
ev = {s["id"]: s["evidence"] for s in r["steps"]}
assert "vorher=rev_old nachher=rev_new" in ev["alembic-vorher-nachher"], ev
assert any(k.startswith("running-image:") for k in ev)
PY
  expect "switch: alembic vor/nach und laufende Image-IDs im Bericht" $?
  make_smoke "$T/smoke.json" PASS "$NEW"
  phase marker --smoke-report "$T/smoke.json"
  expect "marker mit PASS-Bericht: Exit 0" $((RC == 0 ? 0 : 1))
  expect "marker: Datei enthaelt new-sha" $(b marker_is "$NEW")
  expect "marker: atomar (temp-Datei, mv -f, keine Reste)" $(b marker_atomic)
}

t_marker_refusals() {
  new_world; full_to_switch
  make_smoke "$T/s.json" FAIL "$NEW"; phase marker --smoke-report "$T/s.json"
  expect "marker: FAIL-Bericht -> Exit 1, Marker unveraendert" $(b rc_marker 1 "$OLD")
  make_smoke "$T/s.json" PASS "$OLD"; phase marker --smoke-report "$T/s.json"
  expect "marker: Bericht fuer andere SHA -> Exit 1" $(b rc_marker 1 "$OLD")
  make_smoke "$T/s.json" PASS "$NEW" dry; phase marker --smoke-report "$T/s.json"
  expect "marker: Dry-Run-Bericht -> Exit 1" $(b rc_marker 1 "$OLD")
  : > "$T/s.json"; phase marker --smoke-report "$T/s.json"
  expect "marker: unlesbarer Bericht -> Exit 1" $(b rc_marker 1 "$OLD")
  python3 - "$T/stale.json" <<'PY'
import datetime as dt, json, sys
old = (dt.datetime.now(dt.UTC) - dt.timedelta(hours=5)).isoformat(timespec="seconds")
json.dump({"schema_version": 1, "dry_run": False, "result": "PASS", "summary": {"FAIL": 0},
           "target": "audit", "target_sha": "2" * 40, "finished": old}, open(sys.argv[1], "w"))
PY
  phase marker --smoke-report "$T/stale.json"
  expect "marker: veralteter Bericht -> Exit 1" $(b rc_marker 1 "$OLD")
}

t_switch_failures() {
  new_world
  phase baseline; phase pre; phase prep
  FAKE_MIGRATE_TO=wrong_rev phase switch --expect-revision "$REV_NEW"
  expect "switch: alembic != erwartet -> Exit 1" $((RC == 1 ? 0 : 1))
  expect "switch-Abbruch: Marker unveraendert" $(b marker_is "$OLD")
  new_world
  phase baseline; phase pre; phase prep
  FAKE_MIGRATE_TO=$REV_NEW FAKE_UP_WRONG_IMAGE=1 phase switch --expect-revision "$REV_NEW"
  expect "switch: laufendes Image != gebautes Image -> Exit 1" $((RC == 1 ? 0 : 1))
  new_world
  phase baseline; phase pre; phase prep
  FAKE_MIGRATE_TO=$REV_NEW FAKE_TRACEBACK=1 phase switch --expect-revision "$REV_NEW"
  expect "switch: Traceback in Logs -> Exit 1" $((RC == 1 ? 0 : 1))
  new_world
  phase baseline; phase pre
  FAKE_DRYRUN_TOUCHES_PG=1 phase prep
  expect "prep: compose --dry-run beruehrt postgres -> Exit 1, Checkout zurueck auf old-sha" $(b rc_head 1 "$OLD")
  new_world
  phase baseline; phase pre
  printf 'volumes:\n  data: {}\n' > "$W/compose.new"
  phase prep
  expect "prep: Compose-Diff mit volumes -> Exit 1" $((RC == 1 ? 0 : 1))
}

t_rollback() {
  new_world; full_to_switch
  phase rollback
  expect "rollback: Exit 0" $((RC == 0 ? 0 : 1))
  python3 - "$REPORTS" <<'PY'
import glob, json, sys
r = json.load(open(glob.glob(sys.argv[1] + "/release-audit-rollback-*.json")[0]))
steps = {s["id"]: s for s in r["steps"]}
assert all(steps[f"rollback-image:{s}"]["status"] == "PASS" for s in ("api", "web", "worker", "analysis-worker"))
PY
  expect "rollback: laufendes Image == Rollback-Tag-ID je Dienst (im Bericht)" $?
  expect "rollback: HEAD zurueck auf old-sha" $(b head_is "$OLD")
  new_world; full_to_switch
  FAKE_UP_WRONG_IMAGE=1 phase rollback
  expect "rollback: abweichendes laufendes Image -> Exit 1" $((RC == 1 ? 0 : 1))
  grep -q "Rollback-Tag-ID" <<< "$OUT"
  expect "rollback: Fehlermeldung nennt Rollback-Tag-ID" $?
}

t_no_secrets() {
  new_world; full_to_switch
  make_smoke "$T/s.json" PASS "$NEW"; phase marker --smoke-report "$T/s.json"
  phase rollback
  local leaks=0
  grep -rq "$SENTINEL" "$REPORTS" "$W/calls.log" "$MUT_LOG" 2> /dev/null && leaks=1
  grep -q "$SENTINEL" <<< "$OUT" && leaks=1
  expect "Secrets (Env-Datei-Inhalt, PGPASSWORD) tauchen weder in Berichten, Logs noch docker/git-Argumenten auf" $leaks
}

t_static() {
  grep -q '^set -euo pipefail' "$RELEASE"
  expect "statisch: set -euo pipefail" $?
  ! grep -n '|| true' "$RELEASE"
  expect "statisch: kein '|| true' im Release-Skript" $?
  grep -q '^set +x' "$RELEASE"
  expect "statisch: xtrace abgeschaltet" $?
  bash -n "$RELEASE"
  expect "statisch: bash -n" $?
  if command -v shellcheck > /dev/null 2>&1; then
    shellcheck -x "$RELEASE" "${BASH_SOURCE[0]}"
    expect "statisch: shellcheck" $?
  else
    printf 'skip - shellcheck nicht installiert\n'
  fi
}

for t in t_usage_refusals t_pre_report t_pre_failures t_dry_run t_dry_run_detector_catches_broken_guard \
  t_full_cycle t_marker_refusals t_switch_failures t_rollback t_no_secrets t_static; do
  printf '# %s\n' "$t"
  "$t"
done
printf '\n%s bestanden, %s fehlgeschlagen\n' "$PASS_N" "$FAIL_N"
[ "$FAIL_N" -eq 0 ]
