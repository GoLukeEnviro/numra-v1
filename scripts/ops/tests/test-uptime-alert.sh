#!/usr/bin/env bash
# Mock-gh-Test fuer scripts/ops/uptime_alert.sh: Anlegen, Wiederholungs-Begrenzung,
# Kategoriewechsel, Erholung und die Garantie, dass Issue-Texte nur generische Felder
# enthalten. `gh` ist eine Attrappe; es gibt keinen Netzwerkzugriff.
# PYTHON_BIN ueberschreibt den Interpreter (Default python3).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/../uptime_alert.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/bin"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cat >"$WORK/bin/python3" <<EOF
#!/usr/bin/env bash
exec $PYTHON_BIN "\$@"
EOF

# Attrappe: `gh api` liefert Fixtures aus $FIX_*, schreibende Aufrufe landen in $CALLS.
cat >"$WORK/bin/gh" <<'EOF'
#!/usr/bin/env bash
case "$1 $2" in
  "api --paginate")
    case "$3" in
      *"/comments?"*) cat "$FIX_COMMENTS" ;;
      *) cat "$FIX_ISSUES" ;;
    esac ;;
  *) printf '%s\n' "$*" >>"$CALLS" ;;
esac
EOF
chmod +x "$WORK/bin/gh" "$WORK/bin/python3"
export PATH="$WORK/bin:$PATH" CALLS="$WORK/calls" FIX_ISSUES="$WORK/issues" FIX_COMMENTS="$WORK/comments"

# Der ECHTE Titel aus dem Workflow, nicht ein Platzhalter.
TITLE="$(sed -n 's/^ *ALERT_TITLE: "\(.*\)"$/\1/p' "$HERE/../../../.github/workflows/uptime-probe.yml" | tr -d '\r')"
[ -n "$TITLE" ] || { echo "FAIL Titel nicht gefunden"; exit 1; }
NOW_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
OLD_ISO="2020-01-01T00:00:00Z"
fail=0

run() { # run <ok> <category> <code> [prev_failed]
  : >"$CALLS"
  GH_REPO=o/r ALERT_TITLE="$TITLE" PROBE_OK="$1" PROBE_CATEGORY="$2" PROBE_CODE="$3" PREV_FAILED="${4:-true}" \
    RUN_URL=https://example.invalid/run/1 bash "$SCRIPT" >/dev/null
}
expect() { # expect <name> <regex>
  if grep -Eq "$2" "$CALLS"; then echo "ok   $1"; else echo "FAIL $1"; cat "$CALLS"; fail=1; fi
}
expect_none() {
  if [ ! -s "$CALLS" ]; then echo "ok   $1"; else echo "FAIL $1"; cat "$CALLS"; fail=1; fi
}

echo '[]' >"$FIX_ISSUES"
echo '[]' >"$FIX_COMMENTS"
run false database 503 false
expect_none "erster Fehllauf (Vorlauf gruen) -> noch kein Issue"
run "" "" 0 false
expect "Probe ohne Ausgabe -> sofort Monitorfehler-Issue" 'monitor_error'
run false database 503 true
expect "zweiter Fehllauf in Folge -> anlegen" '^issue create'
if grep -Eiq 'avenyth|\.de|numerology|llm|pdf|postgres' "$CALLS"; then
  echo "FAIL Issue-Text enthaelt interne Details"; fail=1
else echo "ok   Issue-Text generisch"; fi

printf '[{"number":7,"title":"%s","body":"x","created_at":"%s"}]' "$TITLE" "$OLD_ISO" >"$FIX_ISSUES"
printf '[{"body":"Kategorie: database (x)","created_at":"%s"}]' "$NOW_ISO" >"$FIX_COMMENTS"
run false database 503
expect_none "gleiche Kategorie, frischer Kommentar -> kein Spam"

# Issue ohne Label (Label entfernt) wird trotzdem gefunden: kein Duplikat.
run false database 503
expect_none "Issue ohne Label gefunden -> kein Duplikat"

run false unreachable 0
expect "Kategoriewechsel -> kommentieren" '^issue comment 7'

printf '[{"body":"Kategorie: database (x)","created_at":"%s"}]' "$OLD_ISO" >"$FIX_COMMENTS"
run false database 503
expect "Erinnerung nach Ablauf -> kommentieren" '^issue comment 7'

run true "" 200
expect "Erholung -> schliessen" '^issue close 7'

echo '[]' >"$FIX_ISSUES"
run true "" 200
expect_none "gesund, kein Issue -> nichts"

exit "$fail"
