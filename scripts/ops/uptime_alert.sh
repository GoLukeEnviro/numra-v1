#!/usr/bin/env bash
# Pflegt das Alarm-Issue des externen Uptime-Probes (genau ein offenes Issue je ALERT_TITLE).
# Die Entscheidung (anlegen / kommentieren / schliessen / nichts) trifft
# `uptime_probe.py decide`: Kommentare nur bei Kategoriewechsel oder alle REMIND_HOURS.
#
# Eingabe (Umgebung): GH_TOKEN, GH_REPO, ALERT_TITLE, ALERT_LABEL (Default uptime-alert),
# PROBE_OK, PROBE_WARN, PROBE_CODE, PROBE_CATEGORY, RUN_URL, REMIND_HOURS (optional).
# Issue-Texte enthalten nur Zeitpunkt, HTTP-Status, Kategorie und Lauf-Link -- keine
# Hostnamen, Dienstnamen oder Diagnosedaten (oeffentliches Repository).
set -euo pipefail

PROBE_OK=${PROBE_OK:-} # leer = Probe lieferte keine Ausgabe -> Monitorfehler (Alarm)
PREV_FAILED=${PREV_FAILED:-true}
: "${GH_REPO:?}" "${ALERT_TITLE:?}" "${RUN_URL:?}"
ALERT_LABEL=${ALERT_LABEL:-uptime-alert}
REMIND_HOURS=${REMIND_HOURS:-6}
PROBE_WARN=${PROBE_WARN:-false}
PROBE_CODE=${PROBE_CODE:-0}
PROBE_CATEGORY=${PROBE_CATEGORY:-}
[ "$PROBE_CODE" != "0" ] || PROBE_CODE="keiner"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

issue="$(gh api --paginate "repos/$GH_REPO/issues?state=open&per_page=100" \
  | jq -s --arg t "$ALERT_TITLE" \
      'add // [] | map(select(.title == $t and (has("pull_request") | not))) | .[0] // empty')"
num="$(jq -r '.number // empty' <<<"${issue:-}")"
last_activity=""
last_text=""
if [ -n "$num" ]; then
  last="$(gh api --paginate "repos/$GH_REPO/issues/$num/comments?per_page=100" | jq -s 'add // [] | last // empty')"
  if [ -n "$last" ]; then
    last_activity="$(jq -r '.created_at' <<<"$last")"
    last_text="$(jq -r '.body // ""' <<<"$last")"
  else
    last_activity="$(jq -r '.created_at' <<<"$issue")"
    last_text="$(jq -r '.body // ""' <<<"$issue")"
  fi
fi

out="$(mktemp)"
trap 'rm -f "$out"' EXIT
GITHUB_OUTPUT="$out" ISSUE_NUMBER="$num" ISSUE_LAST_ACTIVITY="$last_activity" \
  ISSUE_LAST_TEXT="$last_text" REMIND_HOURS="$REMIND_HOURS" \
  PROBE_OK="$PROBE_OK" PROBE_WARN="$PROBE_WARN" PROBE_CATEGORY="$PROBE_CATEGORY" PREV_FAILED="$PREV_FAILED" \
  python3 "$HERE/uptime_probe.py" decide
action="$(sed -n 's/^action=//p' "$out")"
label="$(sed -n 's/^label=//p' "$out")"
PROBE_CATEGORY="$(sed -n 's/^category=//p' "$out")"

details="Zeitpunkt (UTC): $ts
HTTP-Status: $PROBE_CODE
Kategorie: $PROBE_CATEGORY ($label)
Lauf: $RUN_URL"

case "$action" in
  create)
    gh label create "$ALERT_LABEL" --color B60205 --description "Externer Uptime-Probe: Alarm" || true
    gh issue create --title "$ALERT_TITLE" --label "$ALERT_LABEL" --body "Der externe Uptime-Probe meldet eine Stoerung.

$details

Dieses Issue wird bei Erholung automatisch kommentiert und geschlossen. Weitere Kommentare folgen nur bei Aenderung der Kategorie oder nach $REMIND_HOURS Stunden."
    ;;
  comment)
    gh issue comment "$num" --body "Weiterhin bzw. geaendert gestoert.

$details"
    ;;
  close)
    gh issue close "$num" --comment "Wiederhergestellt.

Zeitpunkt (UTC): $ts
HTTP-Status: $PROBE_CODE
Lauf: $RUN_URL"
    ;;
  none) echo "Keine Issue-Aktion noetig." ;;
  *) echo "::error::Unbekannte Aktion: $action"; exit 1 ;;
esac
