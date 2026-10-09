#!/usr/bin/env python3
"""Externer Uptime-Probe: Bewertung, Alarm-Entscheidung und Watchdog (nur Standardbibliothek).

Subcommands (alle lesen Eingaben aus der Umgebung und schreiben nach $GITHUB_OUTPUT):

  probe     TARGET_URL pruefen -> ok, warn, code, category
  decide    PROBE_OK/PROBE_CATEGORY gegen den Zustand des Alarm-Issues -> action
  watchdog  RUNS_FILE (Antwort der Actions-Runs-API) -> ok, category

Sollwerte entsprechen scripts/ops/numra-healthcheck.sh mit
EXPECTED_DEPENDENCIES="database=required numerology_engine=required llm=required pdf=required":
alle vier Dienste muessen `healthy` melden. `degraded` ist nur eine Warnung, `disabled`
bei einem Pflichtdienst eine Konfigurationsabweichung (Alarm), alles andere ein Ausfall.

Die Ausgabe ist bewusst generisch: Zeitpunkt, HTTP-Status und eine grobe Kategorie.
Keine Hostnamen, Dienstnamen, Antwort-Bodies oder Diagnosedaten (das Repository ist
oeffentlich, Issues und Lauf-Logs ebenso).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

REQUIRED_SERVICES = ("database", "numerology_engine", "llm", "pdf")
URL_ALLOWLIST = re.compile(r"^https://avenyth\.de/[A-Za-z0-9._~/?=&%-]*$")
VALUE_PATTERN = re.compile(r"^[a-z_]{1,20}$")
CATEGORY_PATTERN = re.compile(r"Kategorie: ([a-z_]+)")

CATEGORY_LABELS = {
    "unreachable": "Endpunkt nicht erreichbar (Verbindung/Timeout)",
    "http_error": "unerwarteter HTTP-Status",
    "invalid_response": "ungueltige Antwort",
    "readiness": "Gesamtstatus nicht gesund",
    "database": "Datenbank nicht gesund",
    "dependency": "abhaengiger Dienst nicht gesund",
    "config_deviation": "Konfigurationsabweichung",
    "monitor_error": "Fehler im Monitor selbst",
    "monitor_stale": "Monitor hat nicht rechtzeitig gelaufen",
}
# Bei mehreren Befunden gewinnt die schwerwiegendste Kategorie (stabiler Zustandswechsel).
CATEGORY_PRIORITY = ("config_deviation", "database", "dependency", "readiness", "http_error")

DEFAULT_ATTEMPTS = 3
DEFAULT_PAUSE_SECONDS = 20
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_REMIND_HOURS = 6
# Wie der Host-Healthcheck (FAIL_THRESHOLD): ein einzelner Fehllauf ist nur eine Warnung,
# der Alarm braucht den Fehllauf auch im Vorlauf. Sofort alarmieren Konfigurationsabweichung
# (Host: ebenfalls sofort) und Fehler des Monitors selbst.
IMMEDIATE_CATEGORIES = ("config_deviation", "monitor_error", "monitor_stale")
DEFAULT_STALE_MINUTES = 120


@dataclass(frozen=True)
class Verdict:
    ok: bool
    warn: bool
    code: int
    category: str  # "" wenn ok

    @property
    def state(self) -> str:
        return "ok" if self.ok and not self.warn else "warn" if self.ok else "alarm"


@dataclass(frozen=True)
class Response:
    code: int  # 0 = keine HTTP-Antwort (Verbindungsfehler/Timeout)
    body: str


Fetch = Callable[[str, float], Response]


def is_allowed_url(url: str) -> bool:
    return URL_ALLOWLIST.fullmatch(url) is not None


def _clean(value: object) -> str:
    if isinstance(value, str) and VALUE_PATTERN.fullmatch(value):
        return value
    return "missing" if value is None else "invalid"


def evaluate(response: Response) -> Verdict:
    """Bewertet eine einzelne Antwort. Rein, ohne I/O."""
    code = response.code
    if code == 0:
        return Verdict(False, False, 0, "unreachable")
    if code not in (200, 503):
        return Verdict(False, False, code, "http_error")
    try:
        data = json.loads(response.body)
    except ValueError:
        return Verdict(False, False, code, "invalid_response")
    if not isinstance(data, dict) or not isinstance(data.get("status"), str):
        return Verdict(False, False, code, "invalid_response")

    found: set[str] = set()
    warn = False
    for service in REQUIRED_SERVICES:
        value = _clean(data.get(service))
        if value == "healthy":
            continue
        if value == "degraded":
            warn = True
        elif value == "disabled":
            found.add("config_deviation")
        else:
            found.add("database" if service == "database" else "dependency")

    overall = _clean(data["status"])
    if overall == "degraded":
        warn = True
    elif overall != "healthy" and not found:
        found.add("readiness")
    if not found and code != 200:
        found.add("http_error")

    for category in CATEGORY_PRIORITY:
        if category in found:
            return Verdict(False, False, code, category)
    return Verdict(True, warn, code, "")


def http_fetch(url: str, timeout: float) -> Response:
    request = urllib.request.Request(url, headers={"User-Agent": "numra-uptime-probe"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as handle:  # noqa: S310 - URL per Allowlist
            return Response(handle.status, handle.read(1_000_000).decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        return Response(exc.code, exc.read(1_000_000).decode("utf-8", "replace"))
    except (urllib.error.URLError, TimeoutError, OSError):
        return Response(0, "")


def probe(
    url: str,
    *,
    fetch: Fetch = http_fetch,
    sleep: Callable[[float], None] = time.sleep,
    attempts: int = DEFAULT_ATTEMPTS,
    pause: float = DEFAULT_PAUSE_SECONDS,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Verdict:
    """Bis zu `attempts` Versuche; der erste OK-/Warn-Befund beendet die Schleife."""
    verdict = Verdict(False, False, 0, "unreachable")
    for attempt in range(1, attempts + 1):
        verdict = evaluate(fetch(url, timeout))
        if verdict.ok:
            return verdict
        print(f"Versuch {attempt}/{attempts} fehlgeschlagen: {describe(verdict)}")
        if attempt < attempts:
            sleep(pause)
    return verdict


def describe(verdict: Verdict) -> str:
    if verdict.ok:
        return f"HTTP {verdict.code}, " + ("Warnung" if verdict.warn else "gesund")
    return f"HTTP {verdict.code}, {verdict.category}"


def _parse_time(value: str) -> dt.datetime | None:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.UTC)


def decide(
    *,
    ok: bool,
    category: str,
    issue_open: bool,
    warn: bool = False,
    prev_failed: bool = True,
    last_activity: str,
    last_text: str,
    now: dt.datetime,
    remind_hours: float = DEFAULT_REMIND_HOURS,
) -> str:
    """create | comment | close | none -- begrenzt Wiederholungen auf Zustandswechsel/N Stunden."""
    if ok:
        # Eine Warnung (degraded) beendet den Alarm nicht: sonst oeffnet/schliesst ein
        # zwischen degraded und unhealthy flatternder Dienst im Minutentakt Issues.
        return "close" if issue_open and not warn else "none"
    if not issue_open:
        return "create" if prev_failed or category in IMMEDIATE_CATEGORIES else "none"
    match = CATEGORY_PATTERN.search(last_text)
    if match is None or match.group(1) != category:
        return "comment"
    last = _parse_time(last_activity)
    if last is None or now - last >= dt.timedelta(hours=remind_hours):
        return "comment"
    return "none"


def evaluate_heartbeat(
    runs: list[Mapping[str, object]], *, now: dt.datetime, stale_minutes: float
) -> Verdict:
    """Der Monitor lebt, wenn ein abgeschlossener Schedule-Lauf (success/failure) juenger
    als `stale_minutes` ist. `failure` zaehlt mit: ein roter Lauf bei Ausfall des Dienstes
    belegt, dass der Monitor selbst arbeitet."""
    newest: dt.datetime | None = None
    for run in runs:
        if run.get("conclusion") not in ("success", "failure"):
            continue
        created = _parse_time(str(run.get("created_at", "")))
        if created is not None and (newest is None or created > newest):
            newest = created
    if newest is None or now - newest > dt.timedelta(minutes=stale_minutes):
        return Verdict(False, False, 0, "monitor_stale")
    return Verdict(True, False, 0, "")


def _output(values: Mapping[str, str]) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    lines = "".join(f"{key}={value}\n" for key, value in values.items())
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(lines)
    else:
        sys.stdout.write(lines)


def _now() -> dt.datetime:
    override = os.environ.get("NOW")
    return (_parse_time(override) if override else None) or dt.datetime.now(dt.UTC)


def cmd_probe() -> int:
    url = os.environ.get("TARGET_URL", "")
    if not is_allowed_url(url):
        print("::error::target_url ist nicht erlaubt (nur https://avenyth.de/...).")
        return 1
    try:
        verdict = probe(url)
    except Exception:  # noqa: BLE001 - ein Monitor-Fehler darf nie als "alles gut" enden
        verdict = Verdict(False, False, 0, "monitor_error")
    print(f"Ergebnis: {describe(verdict)}")
    _output(
        {
            "ok": str(verdict.ok).lower(),
            "warn": str(verdict.warn).lower(),
            "code": str(verdict.code),
            "category": verdict.category,
        }
    )
    return 0


def cmd_decide() -> int:
    # Fehlende oder unbekannte Probe-Ausgabe (Absturz, Checkout-/Allowlist-Fehler) ist ein
    # Monitorfehler und alarmiert, nie "ok".
    probe_ok = os.environ.get("PROBE_OK")
    category = os.environ.get("PROBE_CATEGORY", "")
    if probe_ok not in ("true", "false"):
        probe_ok, category = "false", "monitor_error"
    action = decide(
        ok=probe_ok == "true",
        warn=os.environ.get("PROBE_WARN") == "true",
        prev_failed=os.environ.get("PREV_FAILED", "true") != "false",
        category=category,
        issue_open=bool(os.environ.get("ISSUE_NUMBER")),
        last_activity=os.environ.get("ISSUE_LAST_ACTIVITY", ""),
        last_text=os.environ.get("ISSUE_LAST_TEXT", ""),
        now=_now(),
        remind_hours=float(os.environ.get("REMIND_HOURS") or DEFAULT_REMIND_HOURS),
    )
    print(f"Aktion: {action}")
    _output(
        {
            "action": action,
            "category": category,
            "label": CATEGORY_LABELS.get(category, "unbekannt"),
        }
    )
    return 0


def cmd_watchdog() -> int:
    try:
        payload = json.loads(Path(os.environ["RUNS_FILE"]).read_text(encoding="utf-8"))
        runs = payload["workflow_runs"]
        if not isinstance(runs, list):
            raise TypeError
    except (KeyError, OSError, ValueError, TypeError):
        # Nicht lesbare Runs-Antwort: Monitorfehler melden, nie stillschweigend "ok".
        verdict = Verdict(False, False, 0, "monitor_error")
    else:
        verdict = evaluate_heartbeat(
            runs,
            now=_now(),
            stale_minutes=float(os.environ.get("STALE_MINUTES") or DEFAULT_STALE_MINUTES),
        )
    print(f"Ergebnis: {'ok' if verdict.ok else verdict.category}")
    _output({"ok": str(verdict.ok).lower(), "category": verdict.category})
    return 0


def main(argv: list[str]) -> int:
    commands = {"probe": cmd_probe, "decide": cmd_decide, "watchdog": cmd_watchdog}
    if len(argv) != 2 or argv[1] not in commands:
        print(f"Aufruf: {argv[0]} {{{'|'.join(commands)}}}", file=sys.stderr)
        return 2
    return commands[argv[1]]()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
