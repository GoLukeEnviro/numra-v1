#!/usr/bin/env bash
# NUMRA restore and rollback drill on an isolated, throw-away environment.
#
#   numra-drill.sh --target audit|prod --config FILE [--dry-run] [--i-am-sure-prod]
#
# Restores the newest logical dump of the target into a private Postgres container, runs the
# candidate migrations on it, then proves both directions with an HTTP probe:
#   * old code (DRILL_OLD_API_IMAGE) against the migrated database  -> rollback R1 viability
#   * new code (DRILL_NEW_API_IMAGE) against the same database      -> forward path
# Only resources named drill-<run>-* (containers, network) and a 0700 work dir are created and
# removed again (trap), the dump copy and env file are truncated before removal. The source
# dump is only read. Passwords and secrets are generated per run, live in 0600 env files and
# are passed with --env-file, never as process arguments. The restored data may contain
# PII: prod therefore needs --i-am-sure-prod. --dry-run only checks dump, images and
# configuration and creates nothing; only the report below REPORT_DIR is written.
#
# Config: the same file as numra-release.sh (see release.env.example) plus DRILL_* values.
# Exit codes: 0 all probes passed, 1 a step failed, 2 usage / refusal.
set +x
set -euo pipefail

readonly SCRIPT_VERSION="1.0.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT_PY="$SCRIPT_DIR/../ops_report/report.py"
PROBE_PY="$SCRIPT_DIR/drill_probe.py"

TARGET="" CONFIG="" DRY_RUN=0 SURE_PROD=0
usage_error() {
  printf 'VERWEIGERT: %s\n' "$*" >&2
  exit 2
}
while [ $# -gt 0 ]; do
  case "$1" in
    --target) TARGET=${2:-}; shift 2 ;;
    --config) CONFIG=${2:-}; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --i-am-sure-prod) SURE_PROD=1; shift ;;
    *) usage_error "unbekannter Parameter: $1" ;;
  esac
done
case "$TARGET" in
  audit | prod) ;;
  *) usage_error "--target audit|prod ist Pflicht (kein Default)" ;;
esac
{ [ -n "$CONFIG" ] && [ -r "$CONFIG" ]; } || usage_error "--config FILE fehlt oder ist nicht lesbar"
# shellcheck source=/dev/null
. "$CONFIG"
for name in CONFIG_TARGET BACKUP_DIR BACKUP_GLOB BACKUP_MAX_AGE_S REPORT_DIR DRILL_WORKDIR \
  DRILL_PG_IMAGE DRILL_REDIS_IMAGE DRILL_OLD_API_IMAGE DRILL_NEW_API_IMAGE DRILL_MIGRATE_IMAGE; do
  [ -n "${!name:-}" ] || usage_error "Konfigwert $name fehlt in $CONFIG"
done
[ "$CONFIG_TARGET" = "$TARGET" ] || usage_error "Konfig gehoert zu CONFIG_TARGET=$CONFIG_TARGET, aufgerufen mit --target $TARGET"
if [ "$TARGET" = "prod" ] && [ "$DRY_RUN" = 0 ] && [ "$SURE_PROD" = 0 ]; then
  usage_error "Drill mit prod-Dump braucht --i-am-sure-prod (Daten koennen PII enthalten)"
fi
SUDO_CMD=${SUDO_CMD-sudo}
DRILL_API_PORT=${DRILL_API_PORT:-8000}
DB_USER=${DB_USER:-numra}
DB_NAME=${DB_NAME:-numra}

command -v python3 > /dev/null 2>&1 || usage_error "python3 fehlt"
mkdir -p "$REPORT_DIR"
RECORDS=$(mktemp "$REPORT_DIR/.records.XXXXXX")
STARTED=$(date -u +%Y-%m-%dT%H:%M:%S+00:00)
ENV_CREATED=0
RUN="drill-$(date -u +%Y%m%d%H%M%S)"
NET="$RUN-net"
D="$DRILL_WORKDIR/$RUN"

say() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$REPORT_DIR/drill.log"; }
chk() {
  printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$RECORDS"
  say "$1 $2 $3"
}
die() {
  chk FAIL abort "$*"
  exit 1
}
priv() { if [ -n "$SUDO_CMD" ]; then $SUDO_CMD "$@"; else "$@"; fi; }

cleanup() {
  local rc=$?
  trap - EXIT
  if [ "$ENV_CREATED" = 1 ]; then
    docker rm -f "$RUN-api-old" "$RUN-api-new" "$RUN-pg" "$RUN-redis" > /dev/null 2>&1 || say "Hinweis: Container waren bereits entfernt"
    docker network rm "$NET" > /dev/null 2>&1 || say "Hinweis: Netzwerk war bereits entfernt"
    if [ -d "$D" ]; then
      : > "$D/prod.dump"
      : > "$D/app.env"
      : > "$D/pg.env"
      rm -rf "$D"
    fi
  fi
  if [ "$rc" -ne 0 ] && ! grep -q '^FAIL' "$RECORDS"; then
    printf 'FAIL\tunexpected-exit\texit=%s\n' "$rc" >> "$RECORDS"
  fi
  local scope limits dry=()
  scope=$(mktemp "$REPORT_DIR/.scope.XXXXXX")
  limits=$(mktemp "$REPORT_DIR/.limits.XXXXXX")
  printf '%s\n' "Restore des juengsten Dumps in isolierte Umgebung" "Kandidaten-Migration auf der Kopie" \
    "HTTP-Sonde: alter Code gegen migrierte DB, neuer Code gegen dieselbe DB" > "$scope"
  printf '%s\n' "Prueft Migrations-Rueckwaertskompatibilitaet nur im Umfang der HTTP-Sonde (Kernpfade, keine LLM-/PDF-Pfade)." \
    "Drill-Daten sind eine Kopie zum Zeitpunkt des Dumps; Last- und Laufzeitverhalten wird nicht gemessen." > "$limits"
  [ "$DRY_RUN" = 0 ] || dry=(--dry-run)
  python3 "$REPORT_PY" render --records "$RECORDS" --out-dir "$REPORT_DIR" --kind drill \
    --target "$TARGET" --target-sha "-" --script numra-drill.sh --script-version "$SCRIPT_VERSION" \
    --started "$STARTED" --scope-file "$scope" --limitations-file "$limits" \
    --extra "phase=drill" --extra "run=$RUN" "${dry[@]}" || rc=1
  rm -f "$RECORDS" "$scope" "$limits"
  exit "$rc"
}
trap cleanup EXIT

# ------------------------------------------------------------------ Vorpruefungen (lesend)

dump=$(priv find "$BACKUP_DIR" -maxdepth 1 -name "$BACKUP_GLOB" -printf '%T@ %p\n' | sort -n | tail -n 1 | cut -d' ' -f2-)
[ -n "$dump" ] || die "kein Dump in $BACKUP_DIR"
age=$(($(date +%s) - $(priv stat -c %Y "$dump")))
[ "$age" -lt "$BACKUP_MAX_AGE_S" ] || die "Dump zu alt (alter_s=$age)"
(cd "$BACKUP_DIR" && priv sha256sum -c --status "$(basename "$dump").sha256") || die "Dump-sha256 stimmt nicht"
chk PASS dump "$(basename "$dump") alter_s=$age, sha256 ok"
for img in "$DRILL_PG_IMAGE" "$DRILL_REDIS_IMAGE" "$DRILL_OLD_API_IMAGE" "$DRILL_NEW_API_IMAGE" "$DRILL_MIGRATE_IMAGE"; do
  docker image inspect "$img" > /dev/null 2>&1 || die "Image fehlt: $img"
done
chk PASS images "alle Drill-Images vorhanden"
if [ "$DRY_RUN" = 1 ]; then
  chk SKIP "plan:drill" "Dry-Run: Umgebung $RUN wuerde erzeugt, Restore, Migration und beide Sonden wuerden laufen"
  exit 0
fi

# ------------------------------------------------------------------ Drill

umask 077
ENV_CREATED=1
mkdir -p "$D"
chmod 700 "$D"
priv cp "$dump" "$D/prod.dump"
priv chown "$(id -u):$(id -g)" "$D/prod.dump"
chmod 600 "$D/prod.dump"
python3 - "$D" "$RUN" "$DB_USER" "$DB_NAME" <<'PY'
import os, secrets, sys

d, run, user, db = sys.argv[1:5]
pw = secrets.token_hex(16)
fd = os.open(os.path.join(d, "pg.env"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f:
    f.write(f"POSTGRES_USER={user}\nPOSTGRES_PASSWORD={pw}\nPOSTGRES_DB={db}\n")
fd = os.open(os.path.join(d, "app.env"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f:
    f.write(
        f"DATABASE_URL=postgresql+asyncpg://{user}:{pw}@{run}-pg:5432/{db}\n"
        f"SESSION_SECRET={secrets.token_hex(24)}\nENVIRONMENT=production\n"
        f"RATE_LIMIT_BACKEND=redis\nREDIS_URL=redis://{run}-redis:6379/0\n"
        'CORS_ALLOWED_ORIGINS=["https://drill.invalid"]\n'
        f"PDF_INTERNAL_URL=http://{run}-pdf:4300\nPDF_INTERNAL_TOKEN={secrets.token_hex(12)}\n"
        "EMAIL_BACKEND=disabled\nNUMRA_LLM_PROVIDER=disabled\nALLOW_SELF_SIGNUP=true\n"
        "EXPORT_STORAGE_DIR=/tmp/exports\n"
    )
PY
docker network create "$NET" > /dev/null || die "Netzwerk"
docker run -d --name "$RUN-pg" --network "$NET" --env-file "$D/pg.env" "$DRILL_PG_IMAGE" > /dev/null || die "Postgres-Start"
docker run -d --name "$RUN-redis" --network "$NET" "$DRILL_REDIS_IMAGE" > /dev/null || die "Redis-Start"
pg_ready=0
for _ in $(seq 1 30); do
  if docker exec "$RUN-pg" pg_isready -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1; then pg_ready=1; break; fi
  sleep 1
done
[ "$pg_ready" = 1 ] || die "Postgres nicht bereit"
chk PASS environment "isolierte Umgebung $RUN bereit"

docker exec -i "$RUN-pg" pg_restore -U "$DB_USER" -d "$DB_NAME" --no-owner --no-privileges < "$D/prod.dump" > "$D/restore.log" 2>&1 \
  || die "Restore fehlgeschlagen (Exit $?)"
chk PASS restore "pg_restore ok, Fehlerzeilen: $(awk 'tolower($0) ~ /error/ { c++ } END { print c + 0 }' "$D/restore.log")"
pgq() { docker exec "$RUN-pg" psql -U "$DB_USER" -d "$DB_NAME" -tAc "$1"; }
alembic_before=$(pgq "select version_num from alembic_version")
chk INFO alembic-restored "$alembic_before"

docker run --rm --network "$NET" --env-file "$D/app.env" -w /app/apps/api "$DRILL_MIGRATE_IMAGE" alembic upgrade head > "$D/mig.log" 2>&1 \
  || die "Kandidaten-Migration fehlgeschlagen"
alembic_after=$(pgq "select version_num from alembic_version")
chk PASS migrate "alembic vorher=$alembic_before nachher=$alembic_after"

run_probe() { # run_probe LABEL IMAGE CONTAINER
  local label=$1
  docker run -d --name "$3" --network "$NET" --env-file "$D/app.env" "$2" > /dev/null || die "$label: Start"
  local up=0
  for _ in $(seq 1 40); do
    if docker exec "$3" python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:$DRILL_API_PORT/v1/health/live',timeout=2)" > /dev/null 2>&1; then up=1; break; fi
    sleep 1
  done
  [ "$up" = 1 ] || die "$label: API nicht erreichbar"
  local out rc=0 tag name code expected status
  out=$(docker exec -e "PORT=$DRILL_API_PORT" -i "$3" python - < "$PROBE_PY" 2>&1) || rc=$?
  while read -r tag name code expected status; do
    [ "$tag" = "PROBE" ] || continue
    chk "$status" "$label:$name" "http=$code erwartet=$expected"
  done <<< "$out"
  [ "$rc" -eq 0 ] || die "$label: Sonde meldet Fehler"
}

run_probe "alter-code" "$DRILL_OLD_API_IMAGE" "$RUN-api-old"
run_probe "neuer-code" "$DRILL_NEW_API_IMAGE" "$RUN-api-new"
chk PASS drill "Restore, Migration und beide Sonden bestanden"
