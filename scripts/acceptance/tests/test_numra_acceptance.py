"""Tests fuer numra_acceptance.py und numra_smoke.py ohne Netz, Docker oder Datenbank."""

import datetime as dt
import http.client
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numra_acceptance as acc  # noqa: E402
import numra_smoke as smoke  # noqa: E402

SHA = "c" * 40
ACC_ARGS = [
    "--target-sha", SHA, "--api-base", "http://127.0.0.1:1", "--web-base", "http://127.0.0.1:2",
    "--container-prefix", "stack-", "--report-dir", "REPORT",
]  # fmt: skip
SMOKE_ARGS = [
    "--target-sha", SHA, "--api-base", "http://127.0.0.1:1", "--web-base", "http://127.0.0.1:2",
    "--container-prefix", "stack-", "--origin", "https://app.example", "--expect-checkins", "503",
    "--report-dir", "REPORT",
]  # fmt: skip


@pytest.fixture(autouse=True)
def no_side_effects(monkeypatch):
    calls = []

    def boom(*args, **kwargs):
        calls.append(args)
        raise AssertionError("Prozess-/Netzaufruf im Test")

    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(http.client.HTTPConnection, "request", boom)
    monkeypatch.setattr(http.client.HTTPSConnection, "request", boom)
    acc.STEPS.clear()
    acc.ST.update(acct={}, cl={}, ids={})
    acc.DRY["on"] = False
    smoke.STEPS.clear()
    smoke.LOCK["on"] = False
    yield calls
    acc.DRY["on"] = False
    smoke.LOCK["on"] = False


def ok_response(code=200):
    return SimpleNamespace(code=code)


# ------------------------------------------------------------------ Acceptance


def test_acceptance_has_no_default_target():
    with pytest.raises(SystemExit):
        acc.main(["--target-sha", SHA])


def test_acceptance_refuses_prod(capsys):
    assert acc.main(["--target", "prod", *ACC_ARGS]) == 2
    assert "nur mit --target audit" in capsys.readouterr().err


def test_acceptance_refuses_short_sha():
    args = [*ACC_ARGS]
    args[1] = "abc123"
    assert acc.main(["--target", "audit", *args]) == 2


def test_acceptance_dry_run_touches_nothing(no_side_effects, capsys, tmp_path):
    args = [a if a != "REPORT" else str(tmp_path / "rep") for a in ACC_ARGS]
    assert acc.main(["--target", "audit", "--dry-run", *args]) == 0
    assert no_side_effects == []
    assert not (tmp_path / "rep").exists()
    assert "DRY-RUN" in capsys.readouterr().out
    with pytest.raises(RuntimeError):
        acc.sh(["docker", "exec", "stack-api-1", "true"])


def test_guard_cmd_only_configured_containers():
    acc.CONTAINERS.update(api="stack-api-1")
    acc.guard_cmd(["docker", "exec", "stack-api-1", "printenv", "X"])
    for bad in (
        ["docker", "exec", "other-api-1", "true"],
        ["docker", "logs", "--since", "1h", "other-api-1"],
        ["docker", "rm", "stack-api-1"],
        ["rm", "-rf", "/"],
        ["git", "checkout", "main"],
    ):
        with pytest.raises(SystemExit):
            acc.guard_cmd(bad)
    acc.guard_cmd(["git", "-C", "/x", "rev-parse", "HEAD"])


def test_client_only_loopback_http():
    acc.Client("http://127.0.0.1:1")
    for url in ("https://127.0.0.1:1", "http://example.org:80", "http://10.0.0.5:1"):
        with pytest.raises(SystemExit):
            acc.Client(url)


def test_synthetic_marker_and_verify_guard(monkeypatch):
    monkeypatch.setattr(acc, "psql", lambda sql: sql)
    acc.ST["acct"]["a"] = {"email": f"{acc.SYNTH_PREFIX}abcdef-a@{acc.SYNTH_DOMAIN}"}
    acc.verify_email_db("a")
    for email in ("real.person@example.com", f"{acc.SYNTH_PREFIX}zz-a@{acc.SYNTH_DOMAIN}"):
        acc.ST["acct"]["a"] = {"email": email}
        with pytest.raises(SystemExit):
            acc.verify_email_db("a")


class FakeClient:
    deleted: list[str] = []

    def __init__(self, role, code=204):
        self.role, self.code = role, code

    def post(self, path, body=None, **kwargs):
        assert path == "/v1/account/delete-all" and body["password"]
        FakeClient.deleted.append(self.role)
        return ok_response(self.code)


def test_cleanup_deletes_every_synthetic_account(monkeypatch):
    FakeClient.deleted = []
    acc.ST["acct"] = {r: {"id": f"id-{r}", "password": "pw"} for r in ("a", "b", "admin")}
    acc.ST["acct"]["x"] = {"id": None, "password": "pw"}
    monkeypatch.setattr(acc, "login", lambda role, label=None: (FakeClient(role), ok_response()))
    answers = iter(["0", "0", "0"])
    monkeypatch.setattr(acc, "psql", lambda sql: next(answers))
    acc.s12_cleanup()
    assert sorted(FakeClient.deleted) == ["a", "admin", "b"]
    assert {s["id"]: s["status"] for s in acc.STEPS} == {
        "12.1": "PASS",
        "12.2": "PASS",
        "12.3": "PASS",
    }


def test_cleanup_failure_is_reported_not_swallowed(monkeypatch):
    FakeClient.deleted = []
    acc.ST["acct"] = {"a": {"id": "id-a", "password": "pw"}}
    monkeypatch.setattr(
        acc, "login", lambda role, label=None: (FakeClient(role, 500), ok_response())
    )
    acc.s12_cleanup()
    assert acc.STEPS[0]["status"] == "FAIL" and len(FakeClient.deleted) == 2


def test_acceptance_report_has_required_fields(tmp_path):
    args = acc.build_parser().parse_args(["--target", "audit", *ACC_ARGS])
    args.report_dir = str(tmp_path)
    acc.rec("1", "eins", "PASS", "ok")
    acc.rec("2", "zwei", "SKIP", "grund")
    acc.ST["env"] = "production"
    assert acc.finish(args, dt.datetime.now(dt.UTC)) == 0
    data = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert data["target_sha"] == SHA and data["script_version"] == acc.SCRIPT_VERSION
    assert data["kind"] == "acceptance" and data["dry_run"] is False
    assert data["summary"]["PASS"] == 1 and data["summary"]["SKIP"] == 1
    assert data["limitations"] and data["scope"]
    assert (
        next(tmp_path.glob("*.md")).read_text(encoding="utf-8").startswith("# Acceptance-Bericht")
    )


def test_acceptance_report_fail_gives_exit_1(tmp_path):
    args = acc.build_parser().parse_args(["--target", "audit", *ACC_ARGS])
    args.report_dir = str(tmp_path)
    acc.rec("1", "eins", "FAIL", "kaputt")
    assert acc.finish(args, dt.datetime.now(dt.UTC)) == 1


def test_no_pdf_skip_left_in_acceptance():
    text = Path(acc.__file__).read_text(encoding="utf-8")
    assert "pdftotext" not in text and "Fallback-Extraktion" not in text
    assert "evaluate_pdf" in text


# ------------------------------------------------------------------ Smoke


def test_smoke_prod_needs_guards(capsys):
    base = ["--target", "prod", *SMOKE_ARGS]
    assert smoke.main(base) == 2
    assert "--i-am-sure-prod" in capsys.readouterr().err
    assert smoke.main([*base, "--i-am-sure-prod"]) == 2
    assert smoke.main([*base, "--i-am-sure-prod", "--confirm-sha", "deadbeef"]) == 2
    assert "--confirm-sha" in capsys.readouterr().err


def test_smoke_has_no_default_target():
    with pytest.raises(SystemExit):
        smoke.main(SMOKE_ARGS)


@pytest.mark.parametrize(
    ("replace", "needle"),
    [
        (("--api-base", "https://api.example"), "Loopback"),
        (("--origin", "ftp://x"), "Origin"),
        (("--web-base", "http://127.0.0.1:1"), "Port"),
    ],
)
def test_smoke_url_validation(replace, needle, capsys):
    args = [*SMOKE_ARGS]
    args[args.index(replace[0]) + 1] = replace[1]
    assert smoke.main(["--target", "audit", *args]) == 2
    assert needle in capsys.readouterr().err


def test_smoke_public_base_only_for_prod(capsys):
    args = [*SMOKE_ARGS, "--public-base", "https://app.example"]
    assert smoke.main(["--target", "audit", *args]) == 2
    assert "nur mit --target prod" in capsys.readouterr().err


def test_smoke_dry_run_prod_touches_nothing(no_side_effects, capsys):
    args = [*SMOKE_ARGS, "--public-base", "https://app.example"]
    assert smoke.main(["--target", "prod", "--dry-run", *args]) == 0
    assert no_side_effects == []
    out = capsys.readouterr().out
    assert "DRY-RUN" in out and "HTTP-Requests=0 Docker-Aufrufe=0" in out
    with pytest.raises(RuntimeError):
        smoke.Client("http://127.0.0.1:1").get("/x")


def test_smoke_report_fields(tmp_path):
    args = smoke.build_parser().parse_args(["--target", "audit", *SMOKE_ARGS])
    args.report_dir, args.public_base = str(tmp_path), None
    smoke.rec("1", "eins", "PASS", "mail=a@b.de")
    assert smoke.finish(args, dt.datetime.now(dt.UTC)) == 0
    data = json.loads(next(tmp_path.glob("smoke-audit-*.json")).read_text(encoding="utf-8"))
    assert data["target_sha"] == SHA and "a@b.de" not in json.dumps(data)
    assert any("public-base" in item for item in data["limitations"])
