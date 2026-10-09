import datetime as dt
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "uptime_probe.py"
spec = importlib.util.spec_from_file_location("uptime_probe", MODULE_PATH)
assert spec is not None and spec.loader is not None
up = importlib.util.module_from_spec(spec)
sys.modules["uptime_probe"] = up
spec.loader.exec_module(up)

NOW = dt.datetime(2026, 10, 9, 12, 0, tzinfo=dt.UTC)
HEALTHY = {"status": "healthy", "database": "healthy", "numerology_engine": "healthy",
           "llm": "healthy", "pdf": "healthy"}  # fmt: skip


def body(**overrides: object) -> str:
    return json.dumps({**HEALTHY, **overrides})


def resp(code: int = 200, text: str | None = None, **overrides: object) -> "up.Response":
    return up.Response(code, body(**overrides) if text is None else text)


# --- evaluate ---------------------------------------------------------------------------


def test_all_healthy_is_ok() -> None:
    verdict = up.evaluate(resp())
    assert (verdict.ok, verdict.warn, verdict.state) == (True, False, "ok")


@pytest.mark.parametrize("service", ["numerology_engine", "llm", "pdf"])
@pytest.mark.parametrize("value", ["unhealthy", "missing_value", "UPPER", "x" * 40])
def test_formerly_optional_service_down_is_alarm(service: str, value: str) -> None:
    verdict = up.evaluate(resp(**{service: value}))
    assert (verdict.ok, verdict.category) == (False, "dependency")


@pytest.mark.parametrize("service", ["numerology_engine", "llm", "pdf"])
def test_formerly_optional_service_disabled_is_config_deviation(service: str) -> None:
    verdict = up.evaluate(resp(**{service: "disabled"}))
    assert (verdict.ok, verdict.category) == (False, "config_deviation")


def test_missing_service_field_is_alarm() -> None:
    data = {k: v for k, v in HEALTHY.items() if k != "llm"}
    verdict = up.evaluate(resp(text=json.dumps(data)))
    assert (verdict.ok, verdict.category) == (False, "dependency")


def test_degraded_is_warning_not_alarm() -> None:
    verdict = up.evaluate(resp(llm="degraded"))
    assert (verdict.ok, verdict.warn, verdict.state) == (True, True, "warn")


def test_database_down_503_is_database_category() -> None:
    verdict = up.evaluate(resp(503, status="unhealthy", database="unhealthy"))
    assert (verdict.ok, verdict.code, verdict.category) == (False, 503, "database")


def test_severity_prefers_config_deviation_over_database() -> None:
    verdict = up.evaluate(resp(database="unhealthy", pdf="disabled"))
    assert verdict.category == "config_deviation"


def test_overall_unhealthy_without_service_cause_is_readiness() -> None:
    verdict = up.evaluate(resp(status="unhealthy"))
    assert verdict.category == "readiness"


def test_503_with_all_services_healthy_is_still_alarm() -> None:
    verdict = up.evaluate(resp(503))
    assert (verdict.ok, verdict.category) == (False, "http_error")


@pytest.mark.parametrize("code", [301, 401, 404, 500, 502, 504])
def test_other_http_codes_are_http_error(code: int) -> None:
    verdict = up.evaluate(up.Response(code, body()))
    assert (verdict.ok, verdict.code, verdict.category) == (False, code, "http_error")


def test_no_response_is_unreachable() -> None:
    verdict = up.evaluate(up.Response(0, ""))
    assert (verdict.ok, verdict.category) == (False, "unreachable")


@pytest.mark.parametrize("text", ["<html>", "[]", '"healthy"', "{}", '{"status": 1}'])
def test_invalid_body_is_invalid_response(text: str) -> None:
    assert up.evaluate(up.Response(200, text)).category == "invalid_response"


# --- probe (Wiederholungen, Timeout, Erholung) -----------------------------------------


def scripted(*responses: object):
    queue = list(responses)
    calls: list[str] = []

    def fetch(url: str, timeout: float) -> "up.Response":
        calls.append(url)
        item = queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    return fetch, calls


def test_probe_recovers_within_attempts() -> None:
    fetch, calls = scripted(up.Response(0, ""), resp())
    sleeps: list[float] = []
    verdict = up.probe("https://avenyth.de/x", fetch=fetch, sleep=sleeps.append)
    assert verdict.ok and len(calls) == 2 and sleeps == [20]


def test_probe_timeout_all_attempts_is_unreachable() -> None:
    fetch, calls = scripted(*[up.Response(0, "")] * 3)
    sleeps: list[float] = []
    verdict = up.probe("https://avenyth.de/x", fetch=fetch, sleep=sleeps.append)
    assert (verdict.ok, verdict.category, len(calls), len(sleeps)) == (False, "unreachable", 3, 2)


def test_http_fetch_maps_timeout_to_no_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise TimeoutError

    monkeypatch.setattr(up.urllib.request, "urlopen", boom)
    assert up.http_fetch("https://avenyth.de/x", 1) == up.Response(0, "")


def test_probe_stops_on_warning_without_retry() -> None:
    fetch, calls = scripted(resp(pdf="degraded"))
    verdict = up.probe("https://avenyth.de/x", fetch=fetch, sleep=lambda _: None)
    assert verdict.state == "warn" and len(calls) == 1


# --- URL-Allowlist ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "allowed"),
    [
        ("https://avenyth.de/api/v1/health/ready", True),
        ("http://avenyth.de/api/v1/health/ready", False),
        ("https://avenyth.de.evil.example/x", False),
        ("https://evil.example/https://avenyth.de/x", False),
        ("https://avenyth.de/x y", False),
        ("", False),
    ],
)
def test_url_allowlist(url: str, allowed: bool) -> None:
    assert up.is_allowed_url(url) is allowed


# --- decide (Alarm-Begrenzung) ----------------------------------------------------------


def decide(**kw: object) -> str:
    base = dict(ok=False, category="database", issue_open=False, last_activity="",
                last_text="", now=NOW)  # fmt: skip
    return up.decide(**{**base, **kw})  # type: ignore[arg-type]


def test_decide_creates_issue_when_none_open() -> None:
    assert decide() == "create"


def test_decide_no_action_when_ok_and_no_issue() -> None:
    assert decide(ok=True, category="") == "none"


def test_decide_closes_on_recovery() -> None:
    assert decide(ok=True, category="", issue_open=True) == "close"


def test_decide_warning_keeps_open_issue_open() -> None:
    assert decide(ok=True, warn=True, category="", issue_open=True) == "none"


def test_decide_suppresses_repeat_within_window() -> None:
    last = (NOW - dt.timedelta(hours=1)).isoformat()
    result = decide(issue_open=True, last_activity=last, last_text="Kategorie: database")
    assert result == "none"


def test_decide_reminds_after_window() -> None:
    last = (NOW - dt.timedelta(hours=6, minutes=1)).isoformat()
    result = decide(issue_open=True, last_activity=last, last_text="Kategorie: database")
    assert result == "comment"


def test_decide_comments_on_category_change_even_if_recent() -> None:
    last = (NOW - dt.timedelta(minutes=5)).isoformat()
    result = decide(issue_open=True, last_activity=last, last_text="Kategorie: unreachable")
    assert result == "comment"


def test_decide_comments_when_state_unreadable() -> None:
    assert decide(issue_open=True, last_activity="kaputt", last_text="") == "comment"


# --- Watchdog (Ausfall des Monitors) ----------------------------------------------------


def run(minutes_ago: float, conclusion: str | None) -> dict[str, object]:
    created = (NOW - dt.timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")
    return {"created_at": created, "conclusion": conclusion}


def test_heartbeat_fresh_success_is_ok() -> None:
    assert up.evaluate_heartbeat([run(40, "success")], now=NOW, stale_minutes=120).ok


def test_heartbeat_fresh_failure_counts_as_alive() -> None:
    assert up.evaluate_heartbeat([run(20, "failure")], now=NOW, stale_minutes=120).ok


def test_heartbeat_stale_is_monitor_stale() -> None:
    verdict = up.evaluate_heartbeat([run(300, "success")], now=NOW, stale_minutes=120)
    assert (verdict.ok, verdict.category) == (False, "monitor_stale")


def test_heartbeat_ignores_cancelled_and_unfinished_runs() -> None:
    runs = [run(5, "cancelled"), run(3, None), run(200, "success")]
    assert not up.evaluate_heartbeat(runs, now=NOW, stale_minutes=120).ok


def test_heartbeat_no_runs_is_stale() -> None:
    assert up.evaluate_heartbeat([], now=NOW, stale_minutes=120).category == "monitor_stale"


# --- CLI --------------------------------------------------------------------------------


def cli(tmp_path: Path, command: str, env: dict[str, str]) -> dict[str, str]:
    out = tmp_path / "out"
    full = {"GITHUB_OUTPUT": str(out), "PATH": "", "NOW": NOW.isoformat(), **env}
    result = subprocess.run(
        [sys.executable, "-I", str(MODULE_PATH), command],
        env=full,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    pairs = (line.split("=", 1) for line in out.read_text(encoding="utf-8").splitlines())
    return {key: value for key, value in pairs}


def test_cli_probe_rejects_foreign_url(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-I", str(MODULE_PATH), "probe"],
        env={"TARGET_URL": "https://evil.example/", "GITHUB_OUTPUT": str(tmp_path / "o")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1 and not (tmp_path / "o").exists()


def test_cli_decide_reminder(tmp_path: Path) -> None:
    env = {
        "PROBE_OK": "false",
        "PROBE_CATEGORY": "database",
        "ISSUE_NUMBER": "7",
        "ISSUE_LAST_ACTIVITY": (NOW - dt.timedelta(hours=2)).isoformat(),
        "ISSUE_LAST_TEXT": "Kategorie: database",
    }
    assert cli(tmp_path, "decide", env) == {"action": "none", "label": "Datenbank nicht gesund"}


def test_cli_watchdog_unreadable_runs_is_monitor_error(tmp_path: Path) -> None:
    runs = tmp_path / "runs.json"
    runs.write_text("kein json", encoding="utf-8")
    assert cli(tmp_path, "watchdog", {"RUNS_FILE": str(runs)}) == {
        "ok": "false",
        "category": "monitor_error",
    }


def test_cli_watchdog_fresh_run(tmp_path: Path) -> None:
    runs = tmp_path / "runs.json"
    runs.write_text(json.dumps({"workflow_runs": [run(30, "success")]}), encoding="utf-8")
    assert cli(tmp_path, "watchdog", {"RUNS_FILE": str(runs)}) == {"ok": "true", "category": ""}
