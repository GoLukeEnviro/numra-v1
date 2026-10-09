#!/usr/bin/env bash
# NUMRA release tooling: phased, configuration-driven deployment of one compose stack.
#
#   numra-release.sh --target audit|prod --config FILE --phase PHASE \
#       --old-sha SHA [--new-sha SHA] [--expect-revision REV] [--smoke-report FILE] \
#       [--dry-run] [--i-am-sure-prod --confirm-sha SHA8]
#
# Phases (each aborts on the first failed check, nothing continues silently):
#   baseline  write the state fingerprint (containers, image IDs, alembic, invariant)
#   pre       read-only: drift vs baseline, marker/HEAD == old, backup age + sha256, disk,
#             readiness; records alembic revision and image IDs
#   prep      no downtime: backups of config/marker, rollback tags (verified against the running
#             image IDs), checkout of the new SHA, compose diff + `compose --dry-run`, build
#   switch    write pause: stop writers, fresh dump, replace compose, migrate, alembic ==
#             --expect-revision, invariant unchanged, recreate, running image == image built in
#             prep, readiness
#   marker    only with a passing, fresh acceptance report for exactly this target and SHA;
#             writes the deployed-SHA marker atomically (temp file + rename)
#   rollback  retag rollback images, restore compose/checkout/marker, recreate, then verify that
#             the image actually running equals the rollback tag ID (mismatch = failure)
#
# --target has no default and is cross-checked against CONFIG_TARGET in the config file, so a
# prod config cannot be used for audit or vice versa. Mutating phases against prod additionally
# need --i-am-sure-prod and --confirm-sha (first 8 characters of the SHA being deployed, for
# rollback of --old-sha). --dry-run runs only the read-only preconditions, prints the plan and
# mutates nothing; the only thing written is the report/log under REPORT_DIR.
#
# Secrets: this script neither reads nor prints env files; they are only handed to
# `docker compose --env-file`. No passwords are handled or passed as process arguments.
# Do not run it with `bash -x` (xtrace is switched off below; it would leak container env).
#
# Configuration: scripts/release/release.env.example, runbook docs/ops/release-tooling.md.
# Exit codes: 0 ok, 1 a check or step failed, 2 usage / refusal.
set +x
set -euo pipefail

readonly SCRIPT_VERSION="1.0.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT_PY="$SCRIPT_DIR/../ops_report/report.py"

TARGET="" CONFIG="" PHASE="" NEW_SHA="" OLD_SHA="" EXPECT_REV="" SMOKE_REPORT=""
DRY_RUN=0 SURE_PROD=0 CONFIRM_SHA=""

usage_error() {
  printf 'VERWEIGERT: %s\n' "$*" >&2
  exit 2
}

while [ $# -gt 0 ]; do
  case "$1" in
    --target) TARGET=${2:-}; shift 2 ;;
    --config) CONFIG=${2:-}; shift 2 ;;
    --phase) PHASE=${2:-}; shift 2 ;;
    --new-sha) NEW_SHA=${2:-}; shift 2 ;;
    --old-sha) OLD_SHA=${2:-}; shift 2 ;;
    --expect-revision) EXPECT_REV=${2:-}; shift 2 ;;
    --smoke-report) SMOKE_REPORT=${2:-}; shift 2 ;;
    --confirm-sha) CONFIRM_SHA=${2:-}; shift 2 ;;
    --i-am-sure-prod) SURE_PROD=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) usage_error "unbekannter Parameter: $1" ;;
  esac
done

case "$TARGET" in
  audit | prod) ;;
  *) usage_error "--target audit|prod ist Pflicht (kein Default)" ;;
esac
case "$PHASE" in
  baseline | pre | prep | switch | marker | rollback) ;;
  *) usage_error "--phase baseline|pre|prep|switch|marker|rollback ist Pflicht" ;;
esac
{ [ -n "$CONFIG" ] && [ -r "$CONFIG" ]; } || usage_error "--config FILE fehlt oder ist nicht lesbar"
sha_re='^[0-9a-f]{40}$'
if [ "$PHASE" != "baseline" ]; then
  [[ $OLD_SHA =~ $sha_re ]] || usage_error "--old-sha (40 Hex) ist Pflicht"
fi
case "$PHASE" in
  pre | prep | switch | marker) [[ $NEW_SHA =~ $sha_re ]] || usage_error "--new-sha (40 Hex) ist Pflicht" ;;
esac
if [ "$PHASE" = "switch" ] && [ -z "$EXPECT_REV" ]; then usage_error "--expect-revision ist fuer switch Pflicht"; fi
if [ "$PHASE" = "marker" ] && [ -z "$SMOKE_REPORT" ]; then usage_error "--smoke-report ist fuer marker Pflicht"; fi

# shellcheck source=/dev/null
. "$CONFIG"

require_cfg() {
  local name
  for name in "$@"; do
    [ -n "${!name:-}" ] || usage_error "Konfigwert $name fehlt in $CONFIG"
  done
}
require_cfg CONFIG_TARGET PROJECT COMPOSE_FILE ENV_FILE REPO_DIR WRITER_SERVICES UNTOUCHED_SERVICES \
  PG_SERVICE DB_USER DB_NAME IMAGE_PREFIX READY_URL MARKER_FILE STATE_DIR REPORT_DIR BACKUP_DIR \
  BACKUP_GLOB BACKUP_MAX_AGE_S FRESH_DUMP_MAX_AGE_S MIN_FREE_GB DISK_PATH RELEASE_BACKUP_ROOT
[ "$CONFIG_TARGET" = "$TARGET" ] || usage_error "Konfig gehoert zu CONFIG_TARGET=$CONFIG_TARGET, aufgerufen mit --target $TARGET"

SUDO_CMD=${SUDO_CMD-sudo}
PROJECT_DIR=${PROJECT_DIR:-}
COMPOSE_SRC_IN_REPO=${COMPOSE_SRC_IN_REPO:-}
COMPOSE_EXTRA_FILES=${COMPOSE_EXTRA_FILES:-}
MIGRATE_SERVICE=${MIGRATE_SERVICE:-}
FLAGS_INIT_SERVICE=${FLAGS_INIT_SERVICE:-}
BUILD_SERVICES=${BUILD_SERVICES:-$WRITER_SERVICES}
BACKUP_FILES=${BACKUP_FILES:-}
BACKUP_SERVICE=${BACKUP_SERVICE:-}
HEALTH_TIMER=${HEALTH_TIMER:-}
INVARIANT_SQL=${INVARIANT_SQL:-}
MAX_SMOKE_AGE_S=${MAX_SMOKE_AGE_S:-3600}
HEALTHY_WAIT_ROUNDS=${HEALTHY_WAIT_ROUNDS:-60}
HEALTHY_WAIT_S=${HEALTHY_WAIT_S:-5}
BASELINE_FILE=${BASELINE_FILE:-$STATE_DIR/baseline-$TARGET.txt}
STATE_FILE="$STATE_DIR/release-$TARGET.state"

DEPLOY_SHA=$NEW_SHA
[ "$PHASE" != "rollback" ] || DEPLOY_SHA=$OLD_SHA
if [ "$DRY_RUN" = 0 ] && [ "$TARGET" = "prod" ]; then
  case "$PHASE" in
    prep | switch | marker | rollback)
      [ "$SURE_PROD" = 1 ] || usage_error "Phase $PHASE gegen prod braucht --i-am-sure-prod"
      { [ -n "$CONFIRM_SHA" ] && [ "$CONFIRM_SHA" = "${DEPLOY_SHA:0:8}" ]; } \
        || usage_error "--confirm-sha muss den ersten 8 Zeichen der zu deployenden SHA entsprechen"
      ;;
  esac
fi

command -v python3 > /dev/null 2>&1 || usage_error "python3 fehlt (Berichtserzeugung)"
mkdir -p "$REPORT_DIR"
RECORDS=$(mktemp "$REPORT_DIR/.records.XXXXXX")
STARTED=$(date -u +%Y-%m-%dT%H:%M:%S+00:00)
RUN_TS=$(date -u +%Y%m%d-%H%M%S)

# ------------------------------------------------------------------ Ausgabe / Bericht

say() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$REPORT_DIR/release.log"; }
chk() { # chk STATUS ID DETAIL
  printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$RECORDS"
  say "$1 $2 $3"
}

PREP_CHECKED_OUT=0
die() {
  chk FAIL abort "$*"
  case "$PHASE" in
    switch) say "HINWEIS: Dienste evtl. gestoppt, Health-Timer evtl. gestoppt. Entscheidung: switch nach Fehlerbehebung wiederholen oder rollback ausfuehren." ;;
    prep)
      if [ "$PREP_CHECKED_OUT" = 1 ]; then
        if git -C "$REPO_DIR" checkout -q --detach "$OLD_SHA"; then
          say "Checkout zurueck auf OLD (prep-Abbruch)"
        else
          say "WARNUNG: Checkout konnte nicht auf OLD zurueckgesetzt werden"
        fi
      fi
      ;;
  esac
  exit 1
}

finish_report() {
  local rc=$?
  trap - EXIT
  if [ "$rc" -ne 0 ] && ! grep -q '^FAIL' "$RECORDS"; then
    printf 'FAIL\tunexpected-exit\texit=%s\n' "$rc" >> "$RECORDS"
  fi
  local scope limits dry=() sha=${DEPLOY_SHA:--}
  scope=$(mktemp "$REPORT_DIR/.scope.XXXXXX")
  limits=$(mktemp "$REPORT_DIR/.limits.XXXXXX")
  printf 'Phase %s gegen Ziel %s (Projekt-Konfiguration %s)\n' "$PHASE" "$TARGET" "$(basename "$CONFIG")" > "$scope"
  printf '%s\n' \
    "Prueft Zustand und Image-IDs der konfigurierten Dienste; keine funktionale Abnahme (Aufgabe des Smoke-/Acceptance-Laufs)." \
    "Datenbank-Restore ist nicht Teil von rollback; Migrationen muessen rueckwaertskompatibel sein (Drill vorab)." \
    "Kein Locking gegen parallele Operatoren; Host-Eingriffe seriell durch genau eine Instanz." > "$limits"
  [ "$DRY_RUN" = 0 ] || dry=(--dry-run)
  python3 "$REPORT_PY" render --records "$RECORDS" --out-dir "$REPORT_DIR" --kind release \
    --target "$TARGET" --target-sha "$sha" --script numra-release.sh --script-version "$SCRIPT_VERSION" \
    --started "$STARTED" --scope-file "$scope" --limitations-file "$limits" \
    --extra "phase=$PHASE" --extra "old_sha=${OLD_SHA:--}" --extra "run=$RUN_TS" \
    "${dry[@]}" || rc=1
  rm -f "$RECORDS" "$scope" "$limits"
  exit "$rc"
}
trap finish_report EXIT

# ------------------------------------------------------------------ Docker / Git / DB (lesend)

container() { printf '%s-%s-1' "$PROJECT" "$1"; }
priv() { if [ -n "$SUDO_CMD" ]; then $SUDO_CMD "$@"; else "$@"; fi; }

DCA=()
build_dca() {
  DCA=(compose -p "$PROJECT" --env-file "$ENV_FILE")
  [ -z "$PROJECT_DIR" ] || DCA+=(--project-directory "$PROJECT_DIR")
  DCA+=(-f "${DC_FILE:-$COMPOSE_FILE}")
  local extra
  for extra in $COMPOSE_EXTRA_FILES; do DCA+=(-f "$extra"); done
}
dc() {
  build_dca
  docker "${DCA[@]}" "$@"
}

pgq() { # nur SELECT; schreibende SQL-Statements sind hier nicht vorgesehen
  case "$1" in
    [Ss][Ee][Ll][Ee][Cc][Tt]\ *) ;;
    *) die "pgq: nur SELECT erlaubt" ;;
  esac
  docker exec "$(container "$PG_SERVICE")" psql -U "$DB_USER" -d "$DB_NAME" -tAc "$1"
}

image_of() { docker inspect -f '{{.Image}}' "$1"; }
image_id() { docker image inspect "$1" -f '{{.Id}}'; }
alembic_rev() { pgq "select version_num from alembic_version"; }

ready_code() {
  local code
  code=$(curl -s -m 10 -o /dev/null -w '%{http_code}' "$READY_URL") || code=000
  printf '%s' "$code"
}

diff_lines() { # diff mit Exit 0/1 gleichgesetzt (1 = Unterschiede), Fehler (>1) bleibt Fehler
  local rc=0
  diff "$1" "$2" || rc=$?
  [ "$rc" -le 1 ]
}

get_state() {
  [ -f "$STATE_FILE" ] || return 0
  awk -F= -v k="$1" '$1 == k { v = substr($0, length(k) + 2) } END { print v }' "$STATE_FILE"
}
set_state() { printf '%s=%s\n' "$1" "$2" >> "$STATE_FILE"; }

fingerprint() {
  docker ps --format '{{.Names}}' | awk -v p="^${PROJECT}-" '$0 ~ p' | sort | while IFS= read -r c; do
    printf 'container %s %s\n' "$c" "$(docker inspect -f '{{.Image}} {{.State.StartedAt}}' "$c")"
  done
  printf 'compose sha=%s\n' "$(sha256sum "$COMPOSE_FILE" | cut -c1-16)"
  printf 'db alembic=%s\n' "$(alembic_rev)"
  if [ -n "$INVARIANT_SQL" ]; then printf 'db invariant=%s\n' "$(pgq "$INVARIANT_SQL")"; fi
}
comparable() { awk '/^(container|compose|db) /' "$1"; }

untouched_ok() {
  local svc c base now
  for svc in $UNTOUCHED_SERVICES; do
    c=$(container "$svc")
    base=$(awk -v p="container $c " 'index($0, p) == 1' "$BASELINE_FILE")
    now="container $c $(docker inspect -f '{{.Image}} {{.State.StartedAt}}' "$c")"
    [ "$base" = "$now" ] || return 1
  done
}

wait_healthy() {
  local i n
  for i in $(seq 1 "$HEALTHY_WAIT_ROUNDS"); do
    n=$(docker ps --filter "name=${PROJECT}-" --format '{{.Status}}' | awk '/unhealthy|starting/ { c++ } END { print c + 0 }')
    [ "$n" = "0" ] && return 0
    sleep "$HEALTHY_WAIT_S"
  done
  return 1
}

newest_dump() {
  priv find "$BACKUP_DIR" -maxdepth 1 -name "$BACKUP_GLOB" -printf '%T@ %p\n' | sort -n | tail -n 1 | cut -d' ' -f2-
}
dump_age() { echo $(($(date +%s) - $(priv stat -c %Y "$1"))); }
dump_sha_ok() { (cd "$BACKUP_DIR" && priv sha256sum -c --status "$(basename "$1").sha256"); }

drift_check() { # Baseline == jetzt (Container, Compose-Hash, alembic, Invariante)
  local tmp
  tmp=$(mktemp "$REPORT_DIR/.fp.XXXXXX")
  fingerprint > "$tmp"
  if diff -q <(comparable "$BASELINE_FILE") <(comparable "$tmp") > /dev/null; then
    chk PASS drift "Ziel entspricht der Baseline"
    rm -f "$tmp"
  else
    rm -f "$tmp"
    die "Ziel weicht von der Baseline ab"
  fi
}

plan() { chk SKIP "plan:$1" "Dry-Run: nicht ausgefuehrt"; }

# ------------------------------------------------------------------ Phasen

phase_baseline() {
  [ -f "$COMPOSE_FILE" ] || die "COMPOSE_FILE nicht vorhanden"
  if [ "$DRY_RUN" = 1 ]; then
    plan "Baseline $BASELINE_FILE schreiben"
    return 0
  fi
  mkdir -p "$STATE_DIR"
  local tmp="$BASELINE_FILE.new"
  fingerprint > "$tmp"
  [ -n "$(awk '/^container /' "$tmp")" ] || die "keine laufenden Container mit Praefix ${PROJECT}-"
  mv -f "$tmp" "$BASELINE_FILE"
  chk PASS baseline "geschrieben: $(awk '/^container /' "$BASELINE_FILE" | wc -l) Container"
}

common_pre() {
  [ -f "$BASELINE_FILE" ] || die "Baseline fehlt ($BASELINE_FILE): zuerst --phase baseline"
  dc config --quiet > /dev/null 2>&1 || die "Compose/env nicht lesbar oder ungueltig"
  chk PASS compose-config "docker compose config ok"
  drift_check
  local marker head
  marker=$(cat "$MARKER_FILE") || die "Marker nicht lesbar"
  head=$(git -C "$REPO_DIR" rev-parse HEAD) || die "HEAD nicht lesbar"
  { [ "$marker" = "$OLD_SHA" ] && [ "$head" = "$OLD_SHA" ]; } || die "Marker/HEAD != old-sha"
  chk PASS marker-head "Marker und HEAD == old-sha"
  local dump age
  dump=$(newest_dump)
  [ -n "$dump" ] || die "kein Dump in $BACKUP_DIR ($BACKUP_GLOB)"
  age=$(dump_age "$dump")
  [ "$age" -lt "$BACKUP_MAX_AGE_S" ] || die "Backup zu alt (alter_s=$age, erlaubt <$BACKUP_MAX_AGE_S)"
  chk PASS backup-age "Dump $(basename "$dump") alter_s=$age (<$BACKUP_MAX_AGE_S)"
  dump_sha_ok "$dump" || die "Backup-sha256 stimmt nicht"
  chk PASS backup-sha256 "sha256 des Dumps ok"
  local free
  free=$(df --output=avail -BG "$DISK_PATH" | tail -n 1 | tr -dc 0-9)
  [ "$free" -gt "$MIN_FREE_GB" ] || die "Platz: ${free}G frei, benoetigt >$MIN_FREE_GB"
  chk PASS disk "frei: ${free}G"
  [ "$(ready_code)" = "200" ] || die "Readiness != 200"
  chk PASS ready "Readiness 200"
  chk INFO alembic-before "$(alembic_rev)"
  local svc
  for svc in $WRITER_SERVICES; do
    chk INFO "image-before:$svc" "$(image_of "$(container "$svc")" | cut -c1-19)"
  done
}

phase_pre() {
  common_pre
  chk PASS pre "Pre-Flight bestanden"
}

compose_diff_forbidden() { # $1 = alte, $2 = neue Compose
  local re
  re="network|volume|^[<>] *($(echo "$UNTOUCHED_SERVICES" | tr ' ' '|')):"
  diff_lines "$1" "$2" | awk -v re="$re" '/^[<>]/ && tolower($0) ~ re { f = 1 } END { exit f ? 0 : 1 }'
}

phase_prep() {
  common_pre
  if [ "$DRY_RUN" = 1 ]; then
    plan "Sicherung nach $RELEASE_BACKUP_ROOT/<TS>"
    plan "Rollback-Tags ${IMAGE_PREFIX}<svc>:rollback-<TS> setzen und gegen laufende Image-IDs pruefen"
    plan "git fetch + checkout --detach ${NEW_SHA:0:8}"
    plan "neue Compose aus dem Repo pruefen (config, compose --dry-run)"
    plan "Build: $BUILD_SERVICES"
    return 0
  fi
  local ts=$RUN_TS rb="$RELEASE_BACKUP_ROOT/$RUN_TS" svc cid f
  mkdir -p "$STATE_DIR"
  : > "$STATE_FILE"
  set_state TS "$ts"
  set_state ALEMBIC_BEFORE "$(alembic_rev)"
  priv install -d -m 0700 "$rb" || die "Sicherungsverzeichnis"
  priv cp -p "$COMPOSE_FILE" "$rb/compose.yml" || die "Sicherung Compose"
  priv cp -p "$MARKER_FILE" "$rb/marker" || die "Sicherung Marker"
  for f in $BACKUP_FILES; do priv cp -p "$f" "$rb/" || die "Sicherung $f"; done
  git -C "$REPO_DIR" rev-parse HEAD | priv tee "$rb/repo_head" > /dev/null
  chk PASS backup-release "Sicherung in $rb"
  for svc in $WRITER_SERVICES; do
    cid=$(image_of "$(container "$svc")") || die "Container $svc fehlt"
    docker tag "$cid" "${IMAGE_PREFIX}${svc}:rollback-$ts" || die "tag $svc"
    [ "$(image_id "${IMAGE_PREFIX}${svc}:rollback-$ts")" = "$cid" ] || die "Rollback-Tag $svc != laufende Image-ID"
    chk PASS "rollback-tag:$svc" "Tag == laufende Image-ID ${cid:0:19}"
  done
  if [ -n "$MIGRATE_SERVICE" ]; then
    cid=$(image_id "${IMAGE_PREFIX}${MIGRATE_SERVICE}:latest") || die "Image $MIGRATE_SERVICE fehlt"
    docker tag "$cid" "${IMAGE_PREFIX}${MIGRATE_SERVICE}:rollback-$ts" || die "tag $MIGRATE_SERVICE"
    [ "$(image_id "${IMAGE_PREFIX}${MIGRATE_SERVICE}:rollback-$ts")" = "$cid" ] || die "Rollback-Tag $MIGRATE_SERVICE != :latest"
    chk PASS "rollback-tag:$MIGRATE_SERVICE" "Tag == :latest ${cid:0:19}"
  fi
  git -C "$REPO_DIR" fetch -q origin || die "git fetch"
  git -C "$REPO_DIR" checkout -q --detach "$NEW_SHA" || die "git checkout"
  PREP_CHECKED_OUT=1
  [ "$(git -C "$REPO_DIR" rev-parse HEAD)" = "$NEW_SHA" ] || die "HEAD != new-sha"
  chk PASS checkout "HEAD == ${NEW_SHA:0:8}"
  local stage="$STATE_DIR/release-$ts"
  if [ -n "$COMPOSE_SRC_IN_REPO" ]; then
    mkdir -p "$stage"
    git -C "$REPO_DIR" show "$NEW_SHA:$COMPOSE_SRC_IN_REPO" > "$stage/compose.new.yml" || die "neue Compose nicht im Repo"
    set_state COMPOSE_NEW "$stage/compose.new.yml"
    chk INFO compose-diff "$(diff_lines "$COMPOSE_FILE" "$stage/compose.new.yml" | awk '/^[<>]/ { c++ } END { print c + 0 }') geaenderte Zeilen"
    if compose_diff_forbidden "$COMPOSE_FILE" "$stage/compose.new.yml"; then
      die "Compose-Diff beruehrt volumes/networks/unveraenderliche Dienste - manuell pruefen"
    fi
    DC_FILE="$stage/compose.new.yml" dc config --quiet > /dev/null || die "neue Compose ungueltig"
    local out u
    # shellcheck disable=SC2086
    out=$(DC_FILE="$stage/compose.new.yml" dc --dry-run up -d --force-recreate --no-deps $WRITER_SERVICES 2>&1) \
      || die "compose --dry-run fehlgeschlagen"
    for u in $UNTOUCHED_SERVICES; do
      if grep -Eiq "(^|[^a-z])${u}([^a-z]|$)" <<< "$out"; then die "compose --dry-run beruehrt $u"; fi
    done
    chk PASS compose-new "neue Compose valide, nur $WRITER_SERVICES betroffen"
  fi
  DC_FILE=${COMPOSE_SRC_IN_REPO:+$stage/compose.new.yml} build_dca
  # shellcheck disable=SC2086
  if ! nice -n 19 docker "${DCA[@]}" build $BUILD_SERVICES $MIGRATE_SERVICE $FLAGS_INIT_SERVICE > "$REPORT_DIR/build-$ts.log" 2>&1; then
    die "Build fehlgeschlagen (Log: $REPORT_DIR/build-$ts.log)"
  fi
  chk PASS build "Build ok"
  for svc in $WRITER_SERVICES; do
    cid=$(image_id "${IMAGE_PREFIX}${svc}:latest")
    set_state "IMG_NEW_$svc" "$cid"
    if [ "$cid" = "$(image_id "${IMAGE_PREFIX}${svc}:rollback-$ts")" ]; then
      chk INFO "image-new:$svc" "identisch mit altem Image (Build-Cache?)"
    else
      chk INFO "image-new:$svc" "${cid:0:19}"
    fi
  done
  drift_check
  untouched_ok || die "unveraenderliche Dienste ($UNTOUCHED_SERVICES) weichen von der Baseline ab"
  chk PASS untouched "$UNTOUCHED_SERVICES unveraendert"
  chk PASS prep "prep abgeschlossen ts=$ts"
}

timer() { # timer stop|start
  [ -z "$HEALTH_TIMER" ] || priv systemctl "$1" "$HEALTH_TIMER"
}

install_compose() { # $1 = Quelle
  local own mode
  own=$(stat -c %U:%G "$COMPOSE_FILE")
  mode=$(stat -c %a "$COMPOSE_FILE")
  priv install -o "${own%%:*}" -g "${own##*:}" -m "$mode" "$1" "$COMPOSE_FILE"
}

phase_switch() {
  local ts rb svc
  ts=$(get_state TS)
  if [ -z "$ts" ]; then
    if [ "$DRY_RUN" = 1 ]; then plan "switch (kein prep-State vorhanden)"; return 0; fi
    die "kein prep-State ($STATE_FILE)"
  fi
  rb="$RELEASE_BACKUP_ROOT/$ts"
  [ "$(git -C "$REPO_DIR" rev-parse HEAD)" = "$NEW_SHA" ] || die "Checkout != new-sha"
  for svc in $WRITER_SERVICES $MIGRATE_SERVICE; do
    docker image inspect "${IMAGE_PREFIX}${svc}:rollback-$ts" > /dev/null 2>&1 || die "Rollback-Tag fehlt: $svc"
  done
  priv test -f "$rb/compose.yml" || die "Compose-Sicherung fehlt"
  untouched_ok || die "unveraenderliche Dienste weichen von der Baseline ab"
  chk PASS switch-pre "Voraussetzungen erfuellt (Checkout, Rollback-Tags, Sicherung, unveraenderliche Dienste)"
  if [ "$DRY_RUN" = 1 ]; then
    plan "Timer stoppen, Schreiber stoppen: $WRITER_SERVICES"
    plan "Backup-Service starten, frischen Dump pruefen (<${FRESH_DUMP_MAX_AGE_S}s)"
    plan "Compose ersetzen, ${MIGRATE_SERVICE:-keine Migration}, alembic == $EXPECT_REV"
    plan "Recreate $WRITER_SERVICES, Image-Gleichheit pruefen, Readiness"
    return 0
  fi
  local t0 before dump age
  t0=$(date +%s)
  before=$(alembic_rev)
  timer stop
  # shellcheck disable=SC2086
  dc stop $WRITER_SERVICES >> "$REPORT_DIR/release.log" 2>&1 || die "Schreiber stoppen"
  chk PASS writers-stopped "Schreiber gestoppt, Readiness jetzt $(ready_code)"
  if [ -n "$BACKUP_SERVICE" ]; then priv systemctl start "$BACKUP_SERVICE" || die "Backup-Service"; fi
  dump=$(newest_dump)
  age=$(dump_age "$dump")
  [ "$age" -lt "$FRESH_DUMP_MAX_AGE_S" ] || die "kein frischer Pre-Deploy-Dump (alter_s=$age)"
  dump_sha_ok "$dump" || die "Pre-Deploy-Dump sha256"
  set_state DUMP "$(basename "$dump")"
  chk PASS predeploy-dump "$(basename "$dump") alter_s=$age"
  local new_compose
  new_compose=$(get_state COMPOSE_NEW)
  if [ -n "$new_compose" ]; then
    install_compose "$new_compose" || die "Compose installieren"
    chk PASS compose-installed "Compose ersetzt (sha256 $(sha256sum "$COMPOSE_FILE" | cut -c1-16))"
  fi
  local inv_before=""
  [ -z "$INVARIANT_SQL" ] || inv_before=$(pgq "$INVARIANT_SQL")
  if [ -n "$MIGRATE_SERVICE" ]; then
    dc run --rm --no-deps -T "$MIGRATE_SERVICE" >> "$REPORT_DIR/release.log" 2>&1 || die "Migration fehlgeschlagen"
  fi
  local after
  after=$(alembic_rev)
  chk INFO alembic-vorher-nachher "vorher=$before nachher=$after"
  [ "$after" = "$EXPECT_REV" ] || die "alembic ($after) != erwartete Revision ($EXPECT_REV)"
  chk PASS alembic "alembic == $EXPECT_REV"
  if [ -n "$FLAGS_INIT_SERVICE" ]; then
    dc run --rm --no-deps -T "$FLAGS_INIT_SERVICE" >> "$REPORT_DIR/release.log" 2>&1 || die "$FLAGS_INIT_SERVICE fehlgeschlagen"
  fi
  if [ -n "$INVARIANT_SQL" ]; then
    [ "$(pgq "$INVARIANT_SQL")" = "$inv_before" ] || die "Invariante (INVARIANT_SQL) hat sich geaendert"
    chk PASS invariant "Invariante unveraendert"
  fi
  # shellcheck disable=SC2086
  dc up -d --force-recreate --no-deps $WRITER_SERVICES >> "$REPORT_DIR/release.log" 2>&1 || die "up fehlgeschlagen"
  wait_healthy || die "Container unhealthy/starting nach Wartezeit"
  for svc in $WRITER_SERVICES; do
    [ "$(image_of "$(container "$svc")")" = "$(get_state "IMG_NEW_$svc")" ] || die "$svc laeuft nicht auf dem in prep gebauten Image"
    chk PASS "running-image:$svc" "laufendes Image == in prep gebautes Image"
  done
  untouched_ok || die "unveraenderliche Dienste wurden veraendert"
  chk PASS untouched "$UNTOUCHED_SERVICES unveraendert (Image-ID + StartedAt)"
  [ "$(ready_code)" = "200" ] || die "Readiness != 200 nach switch"
  chk PASS ready "Readiness 200"
  local tb
  for svc in $WRITER_SERVICES; do
    tb=$(docker logs --since 3m "$(container "$svc")" 2>&1 | awk '/Traceback/ { c++ } END { print c + 0 }')
    if [ "$tb" -eq 0 ]; then chk PASS "log:$svc" "0 Tracebacks (3 min)"; else die "$svc: $tb Tracebacks in den letzten 3 min"; fi
  done
  timer start
  set_state ALEMBIC_AFTER "$after"
  set_state SWITCH_OK 1
  chk PASS switch "switch ok, Fenster s=$(($(date +%s) - t0)); Marker NICHT gesetzt"
}

phase_marker() {
  if [ "$(get_state SWITCH_OK)" != "1" ]; then
    if [ "$DRY_RUN" = 1 ]; then plan "marker (switch nicht abgeschlossen)"; return 0; fi
    die "switch nicht erfolgreich abgeschlossen"
  fi
  [ "$(git -C "$REPO_DIR" rev-parse HEAD)" = "$NEW_SHA" ] || die "Checkout != new-sha"
  [ "$(ready_code)" = "200" ] || die "Readiness != 200"
  local verdict
  verdict=$(python3 "$REPORT_PY" check-smoke --report "$SMOKE_REPORT" --target "$TARGET" --sha "$NEW_SHA" --max-age-s "$MAX_SMOKE_AGE_S") \
    || die "Abnahmebericht abgelehnt: $verdict"
  chk PASS smoke-report "$verdict"
  if [ "$DRY_RUN" = 1 ]; then
    plan "Marker atomar auf ${NEW_SHA:0:8} setzen (temp + rename)"
    return 0
  fi
  local tmp="$MARKER_FILE.new"
  printf '%s\n' "$NEW_SHA" | priv tee "$tmp" > /dev/null
  priv chown --reference="$MARKER_FILE" "$tmp"
  priv chmod --reference="$MARKER_FILE" "$tmp"
  priv mv -f "$tmp" "$MARKER_FILE"
  [ "$(cat "$MARKER_FILE")" = "$NEW_SHA" ] || die "Marker nach Schreiben != new-sha"
  chk PASS marker "Marker == ${NEW_SHA:0:8}"
}

phase_rollback() {
  local ts rb svc
  ts=$(get_state TS)
  if [ -z "$ts" ]; then
    if [ "$DRY_RUN" = 1 ]; then plan "rollback (kein prep-State vorhanden)"; return 0; fi
    die "kein prep-State ($STATE_FILE)"
  fi
  rb="$RELEASE_BACKUP_ROOT/$ts"
  for svc in $WRITER_SERVICES $MIGRATE_SERVICE; do
    docker image inspect "${IMAGE_PREFIX}${svc}:rollback-$ts" > /dev/null 2>&1 || die "Rollback-Tag fehlt: $svc (vor dem Stoppen abgebrochen)"
  done
  priv test -f "$rb/compose.yml" || die "Compose-Sicherung fehlt (vor dem Stoppen abgebrochen)"
  chk PASS rollback-pre "Rollback-Tags und Compose-Sicherung vorhanden"
  if [ "$DRY_RUN" = 1 ]; then
    plan "Schreiber stoppen, Rollback-Tags nach :latest, Compose/Checkout/Marker zurueck"
    plan "Recreate --no-build, laufendes Image == Rollback-Tag-ID pruefen"
    return 0
  fi
  timer stop
  # shellcheck disable=SC2086
  dc stop $WRITER_SERVICES >> "$REPORT_DIR/release.log" 2>&1 || die "Schreiber stoppen"
  for svc in $WRITER_SERVICES $MIGRATE_SERVICE; do
    docker tag "${IMAGE_PREFIX}${svc}:rollback-$ts" "${IMAGE_PREFIX}${svc}:latest" || die "retag $svc"
  done
  install_compose "$rb/compose.yml" || die "Compose zurueck"
  git -C "$REPO_DIR" checkout -q --detach "$OLD_SHA" || die "checkout old-sha"
  if [ "$(cat "$MARKER_FILE")" != "$OLD_SHA" ]; then
    priv cp -p "$rb/marker" "$MARKER_FILE.new" && priv mv -f "$MARKER_FILE.new" "$MARKER_FILE" || die "Marker zuruecksetzen"
    chk INFO marker "Marker auf old-sha zurueckgesetzt"
  fi
  # shellcheck disable=SC2086
  dc up -d --force-recreate --no-deps --no-build $WRITER_SERVICES >> "$REPORT_DIR/release.log" 2>&1 || die "up fehlgeschlagen"
  wait_healthy || die "Container unhealthy/starting nach Wartezeit"
  local want got
  for svc in $WRITER_SERVICES; do
    want=$(image_id "${IMAGE_PREFIX}${svc}:rollback-$ts")
    got=$(image_of "$(container "$svc")")
    [ "$got" = "$want" ] || die "$svc: laufendes Image ${got:0:19} != Rollback-Tag-ID ${want:0:19}"
    chk PASS "rollback-image:$svc" "laufendes Image == Rollback-Tag-ID ${want:0:19}"
  done
  untouched_ok && chk PASS untouched "$UNTOUCHED_SERVICES unveraendert" || chk FAIL untouched "$UNTOUCHED_SERVICES weichen von der Baseline ab"
  [ "$(git -C "$REPO_DIR" rev-parse HEAD)" = "$OLD_SHA" ] || die "HEAD != old-sha"
  [ "$(ready_code)" = "200" ] || die "Readiness != 200 nach rollback"
  chk PASS ready "Readiness 200"
  timer start
  chk INFO alembic-after-rollback "$(alembic_rev) (DB wird nicht zurueckgerollt)"
  chk PASS rollback "Rollback abgeschlossen"
}

"phase_$PHASE"
