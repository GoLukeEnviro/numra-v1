"""Tests fuer scripts/ops_report/report.py."""

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest
import report

SHA = "a" * 40


def make_report(**overrides):
    steps = [
        {"id": "1", "name": "eins", "status": "PASS", "evidence": "ok"},
        {"id": "2", "name": "zwei", "status": "SKIP", "evidence": "n/a"},
    ]
    data = {
        "kind": "acceptance",
        "target": "audit",
        "target_sha": SHA,
        "script": "t.py",
        "script_version": "1",
        "started": "2026-01-01T00:00:00+00:00",
        "finished": report.now_iso(),
        "scope": ["Umfang A"],
        "steps": steps,
        "limitations": ["Grenze B"],
    }
    data.update(overrides)
    return report.build_report(**data)


def test_redact_removes_secret_mail_uuid_token():
    text = (
        "pw=geheim123 mail=a@b.de id=12345678-1234-1234-1234-123456789abc "
        "tok=" + "x" * 40 + " sha=" + SHA
    )
    out = report.redact(text, secrets=("geheim123",))
    assert "geheim123" not in out
    assert "a@b.de" not in out
    assert "<email>" in out and "12345678.." in out and "<tok>" in out
    assert SHA in out


def test_redact_keeps_synthetic_mail_prefix():
    assert "acc-1@example.com" in report.redact("acc-1@example.com x@y.de", keep_prefix="acc-")


def test_result_and_summary():
    assert make_report()["result"] == "PASS"
    failing = make_report(steps=[{"id": "1", "name": "n", "status": "FAIL", "evidence": ""}])
    assert failing["result"] == "FAIL"
    assert make_report(steps=[])["result"] == "FAIL"
    only_skip = [{"id": "1", "name": "n", "status": "SKIP", "evidence": ""}]
    assert make_report(steps=only_skip)["result"] == "FAIL"
    assert make_report(steps=only_skip, dry_run=True)["result"] == "PASS"


def test_unknown_status_rejected():
    with pytest.raises(ValueError):
        make_report(steps=[{"id": "1", "name": "n", "status": "OK", "evidence": ""}])


def test_markdown_contains_required_fields():
    md = report.render_markdown(make_report())
    for needle in ("**PASS**", SHA, "Skriptversion", "Umfang A", "Grenze B", "| 1 | PASS |"):
        assert needle in md


def test_write_report_files_private(tmp_path):
    json_path, md_path = report.write_report(make_report(), tmp_path / "out", "stem")
    assert json.loads(json_path.read_text(encoding="utf-8"))["target_sha"] == SHA
    assert md_path.read_text(encoding="utf-8").startswith("# ")
    if sys.platform != "win32":
        assert json_path.stat().st_mode & 0o077 == 0


def write_json(tmp_path, data):
    path = tmp_path / "r.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_check_smoke_accepts_fresh_pass(tmp_path):
    path = write_json(tmp_path, make_report())
    assert report.check_smoke_report(path, "audit", SHA) == (True, "ok")


@pytest.mark.parametrize(
    ("mutation", "needle"),
    [
        ({"dry_run": True}, "Dry-Run"),
        ({"result": "FAIL"}, "nicht PASS"),
        ({"target": "prod"}, "Ziel"),
        ({"target_sha": "b" * 40}, "SHA"),
        ({"schema_version": 99}, "Schema"),
        ({"finished": "2020-01-01T00:00:00+00:00"}, "alt"),
    ],
)
def test_check_smoke_rejects(tmp_path, mutation, needle):
    data = make_report() | mutation
    ok, reason = report.check_smoke_report(write_json(tmp_path, data), "audit", SHA)
    assert not ok and needle in reason


def test_check_smoke_rejects_future_and_garbage(tmp_path):
    future = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=2)).isoformat()
    data = make_report() | {"finished": future}
    assert not report.check_smoke_report(write_json(tmp_path, data), "audit", SHA)[0]
    bad = tmp_path / "bad.json"
    bad.write_text("kein json", encoding="utf-8")
    assert not report.check_smoke_report(bad, "audit", SHA)[0]
    assert not report.check_smoke_report(tmp_path / "fehlt.json", "audit", SHA)[0]


def test_cli_render_and_check(tmp_path):
    script = Path(report.__file__)
    records = tmp_path / "rec.tsv"
    records.write_text("PASS\tcheck\tok mail=a@b.de\nINFO\tnote\tx\n", encoding="utf-8")
    base = [sys.executable, str(script), "render", "--records", str(records)]
    args = [
        "--out-dir", str(tmp_path / "o"), "--kind", "acceptance", "--target", "audit",
        "--target-sha", SHA, "--script", "s", "--script-version", "1",
        "--started", "2026-01-01T00:00:00+00:00", "--extra", "phase=x",
    ]  # fmt: skip
    done = subprocess.run(base + args, capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    produced = next((tmp_path / "o").glob("*.json"))
    assert "a@b.de" not in produced.read_text(encoding="utf-8")
    check = [sys.executable, str(script), "check-smoke", "--report", str(produced)]
    ok = subprocess.run(
        check + ["--target", "audit", "--sha", SHA], capture_output=True, check=False
    )
    wrong = subprocess.run(
        check + ["--target", "audit", "--sha", "c" * 40], capture_output=True, check=False
    )
    assert ok.returncode == 0 and wrong.returncode == 1
