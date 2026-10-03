#!/usr/bin/env bash
# Mock-docker/curl harness for scripts/ops/numra-healthcheck.sh -- A6 (stale QUEUED
# job alarm). Runs the real script against fake `docker`/`curl` binaries so it never
# touches a real stack; exercises both the "all clear" and "stale queued" paths. Exits
# non-zero (and prints the failing case) on any mismatch.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HEALTHCHECK="$SCRIPT_DIR/../numra-healthcheck.sh"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

FAKE_BIN="$WORK/bin"
mkdir -p "$FAKE_BIN" "$WORK/backups" "$WORK/state"

# `docker exec -i <container> psql ... -c "<sql>"` -- the real script only ever reads
# the fixed four-column counts row; this stub ignores the SQL and returns whatever
# $WORK/psql-output says, so each case below just rewrites that one file.
cat > "$FAKE_BIN/docker" <<'EOF'
#!/usr/bin/env bash
cat "$PSQL_OUTPUT_FILE"
EOF
chmod +x "$FAKE_BIN/docker"

cat > "$FAKE_BIN/curl" <<'EOF'
#!/usr/bin/env bash
echo '{"status":"healthy"}'
EOF
chmod +x "$FAKE_BIN/curl"

export PATH="$FAKE_BIN:$PATH"
export PSQL_OUTPUT_FILE="$WORK/psql-output"
touch "$WORK/backups/numra-fresh.dump"

# STATUS_FILE/BACKUP_DIR/CONFIG_FILE itself are plain assignments in the real script
# (not `${VAR-default}`), so they can't be overridden via the environment -- only via
# the config file the script already sources (`/etc/numra/healthcheck.env`). This test
# therefore owns that one real path for its duration and restores whatever was there.
CONFIG_PATH=/etc/numra/healthcheck.env
CONFIG_BACKUP="$WORK/healthcheck.env.orig"
[ -e "$CONFIG_PATH" ] && cp "$CONFIG_PATH" "$CONFIG_BACKUP" || CONFIG_BACKUP=""
restore_config() {
  if [ -n "$CONFIG_BACKUP" ]; then cp "$CONFIG_BACKUP" "$CONFIG_PATH"; else rm -f "$CONFIG_PATH"; fi
}
trap 'restore_config; rm -rf "$WORK"' EXIT
mkdir -p "$(dirname "$CONFIG_PATH")"
cat > "$CONFIG_PATH" <<EOF
STATUS_FILE="$WORK/state/health-status.json"
BACKUP_DIR="$WORK/backups"
PROD_READY_URL="http://fake/ready"
PROD_DB_CONTAINER=fake-prod
AUDIT_READY_URL=
EOF

run_case() {
  local label="$1" counts="$2" expect_exit="$3"
  printf '%s\n' "$counts" > "$PSQL_OUTPUT_FILE"
  rm -f "$WORK/state/health-status.json"
  set +e
  bash "$HEALTHCHECK" > "$WORK/out" 2> "$WORK/err"
  local actual_exit=$?
  set -e
  if [ "$actual_exit" -ne "$expect_exit" ]; then
    echo "FAIL [$label]: expected exit $expect_exit, got $actual_exit" >&2
    echo "--- stdout ---"; cat "$WORK/out" >&2
    echo "--- stderr ---"; cat "$WORK/err" >&2
    exit 1
  fi
  echo "ok [$label]"
}

# failed=0, failed_24h=0, stale_queued=0 -> all clear.
run_case "no stale queued jobs" "0 0 0 0" 0

# failed=0, failed_24h=0, stale_queued=3 -> alarm, and the status file names it.
run_case "stale queued jobs trip the alarm" "0 0 0 3" 1
if ! grep -q "stale_queued" "$WORK/state/health-status.json"; then
  echo "FAIL: status file does not record stale_queued" >&2
  cat "$WORK/state/health-status.json" >&2
  exit 1
fi
if ! grep -q "stale_queued_job" "$WORK/err"; then
  echo "FAIL: stderr does not name the stale-queued failure" >&2
  cat "$WORK/err" >&2
  exit 1
fi
echo "ok [status file + stderr name the stale-queued failure]"

echo "all numra-healthcheck.sh stale-queued tests passed"
