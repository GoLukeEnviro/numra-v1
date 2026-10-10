"""Tests fuer numra_acceptance.py, numra_smoke.py und stack_config ohne Netz, Docker oder DB."""

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
import stack_config  # noqa: E402

SHA = "c" * 40
REPO = Path(__file__).resolve().parents[3]


def write_stack(tmp_path, target="audit", project="stack-a", port=1, name=None):
    path = tmp_path / (name or f"{target}.env")
    path.write_text(
        f"CONFIG_TARGET={target}\nPROJECT={project}  # Kommentar\n"
        f'READY_URL="http://127.0.0.1:{port}/v1/health/ready"\nSUDO_CMD=sudo\n',
        encoding="utf-8",
    )
    return str(path)


def acc_args(tmp_path, stack=None, **over):
    args = {
        "--target-sha": SHA,
        "--api-base": "http://127.0.0.1:1",
        "--web-base": "http://127.0.0.1:2",
        "--stack-config": stack or write_stack(tmp_path),
        "--repo-dir": "/repo",
        "--report-dir": str(tmp_path / "rep"),
    }
    args.update(over)
    return [x for kv in args.items() for x in kv]


def smoke_args(tmp_path, stack=None, **over):
    args = {
        "--target-sha": SHA,
        "--api-base": "http://127.0.0.1:1",
        "--web-base": "http://127.0.0.1:2",
        "--stack-config": stack or write_stack(tmp_path),
        "--repo-dir": "/repo",
        "--origin": "https://app.example",
        "--expect-checkins": "503",
        "--report-dir": str(tmp_path / "rep"),
    }
    args.update(over)
    return [x for kv in args.items() for x in kv]


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
    acc.ST.clear()
    acc.ST.update(acct={}, cl={}, ids={})
    acc.DRY["on"] = False
    smoke.STEPS.clear()
    smoke.LOCK["on"] = False
    yield calls
    acc.DRY["on"] = False
    smoke.LOCK["on"] = False


def resp(code=200):
    return SimpleNamespace(code=code)


# ------------------------------------------------------------------ stack_config


def test_stack_config_parses_without_executing(tmp_path):
    values = stack_config.load(write_stack(tmp_path, project="p1", port=17800))
    assert values["PROJECT"] == "p1" and values["CONFIG_TARGET"] == "audit"
    assert values["READY_URL"].endswith(":17800/v1/health/ready")


def test_stack_config_requires_keys(tmp_path):
    path = tmp_path / "x.env"
    path.write_text("PROJECT=a\n", encoding="utf-8")
    with pytest.raises(stack_config.StackRefusalError):
        stack_config.load(path)
    with pytest.raises(stack_config.StackRefusalError):
        stack_config.load(tmp_path / "fehlt.env")


def test_stack_bind_target_port_and_prefix(tmp_path):
    stack = stack_config.load(write_stack(tmp_path, port=17801))
    assert stack_config.bind("audit", "http://127.0.0.1:17801", stack) == "stack-a-"
    with pytest.raises(stack_config.StackRefusalError):
        stack_config.bind("prod", "http://127.0.0.1:17801", stack)
    with pytest.raises(stack_config.StackRefusalError):
        stack_config.bind("audit", "http://127.0.0.1:17800", stack)


@pytest.mark.parametrize(("backend", "allow", "ok"), [
    ("disabled", False, True), ("", False, True), ("logging", False, True),
    ("smtp", False, False), ("smtp", True, True), ("sendgrid", True, False),
])  # fmt: skip
def test_mail_backend_policy(backend, allow, ok):
    if ok:
        stack_config.check_mail_backend(backend, allow)
    else:
        with pytest.raises(stack_config.StackRefusalError):
            stack_config.check_mail_backend(backend, allow)


# ------------------------------------------------------------------ Acceptance


def test_acceptance_has_no_default_target(tmp_path):
    with pytest.raises(SystemExit):
        acc.main(acc_args(tmp_path))


def test_acceptance_refuses_prod(tmp_path, capsys):
    stack = write_stack(tmp_path, target="prod")
    assert acc.main(["--target", "prod", *acc_args(tmp_path, stack)]) == 2
    assert "nur mit --target audit" in capsys.readouterr().err


def test_acceptance_refuses_prod_stack_with_audit_target(tmp_path, capsys):
    """Prod-Konfig/-Port mit --target audit: Abbruch."""
    stack = write_stack(tmp_path, target="prod", project="stack-prod", port=1)
    assert acc.main(["--target", "audit", *acc_args(tmp_path, stack)]) == 2
    assert "CONFIG_TARGET=prod" in capsys.readouterr().err


def test_acceptance_refuses_foreign_api_port(tmp_path, capsys):
    args = acc_args(tmp_path, **{"--api-base": "http://127.0.0.1:17800"})
    assert acc.main(["--target", "audit", *args]) == 2
    assert "READY_URL-Port" in capsys.readouterr().err


def test_acceptance_requires_repo_dir(tmp_path):
    args = acc_args(tmp_path)
    i = args.index("--repo-dir")
    del args[i : i + 2]
    with pytest.raises(SystemExit):
        acc.main(["--target", "audit", *args])


def test_acceptance_refuses_short_sha(tmp_path):
    assert acc.main(["--target", "audit", *acc_args(tmp_path, **{"--target-sha": "abc123"})]) == 2


def test_acceptance_dry_run_touches_nothing(no_side_effects, capsys, tmp_path):
    assert acc.main(["--target", "audit", "--dry-run", *acc_args(tmp_path)]) == 0
    assert no_side_effects == []
    assert not (tmp_path / "rep").exists()
    assert "DRY-RUN" in capsys.readouterr().out
    with pytest.raises(RuntimeError):
        acc.sh(["docker", "exec", "stack-a-api-1", "true"])


def scripted_sh(answers):
    def fake(args, stdin=None, timeout=120):
        key = args[-1]
        for needle, value in answers.items():
            if needle in key or needle in args:
                return value
        return (1, "")

    return fake


def configured_acc(tmp_path, monkeypatch, **answers):
    args = acc.build_parser().parse_args(["--target", "audit", *acc_args(tmp_path)])
    acc.configure(args)
    defaults = {
        "ENVIRONMENT": (0, "production\n"),
        "rev-parse": (0, SHA + "\n"),
        "EMAIL_BACKEND": (0, "disabled\n"),
    }
    defaults.update(answers)
    monkeypatch.setattr(acc, "sh", scripted_sh(defaults))
    return args


def test_acceptance_unset_mail_backend_means_default_disabled(tmp_path, monkeypatch):
    args = configured_acc(tmp_path, monkeypatch, EMAIL_BACKEND=(0, "__unset__"))
    acc.preflight(args)
    assert acc.ST["mail_backend"] == "disabled"


def test_acceptance_preflight_ok(tmp_path, monkeypatch):
    args = configured_acc(tmp_path, monkeypatch)
    assert acc.preflight(args) == SHA
    assert acc.ST["env"] == "production" and acc.ST["mail_backend"] == "disabled"


@pytest.mark.parametrize(
    ("answers", "needle"),
    [
        ({"ENVIRONMENT": (1, "")}, "ENVIRONMENT"),
        ({"ENVIRONMENT": (0, "\n")}, "ENVIRONMENT"),
        ({"rev-parse": (0, "d" * 40 + "\n")}, "HEAD"),
        ({"rev-parse": (128, "")}, "HEAD"),
        ({"EMAIL_BACKEND": (0, "smtp\n")}, "EMAIL_BACKEND"),
        ({"EMAIL_BACKEND": (1, "Error: No such container")}, "EMAIL_BACKEND"),
    ],
)
def test_acceptance_preflight_aborts(tmp_path, monkeypatch, answers, needle):
    args = configured_acc(tmp_path, monkeypatch, **answers)
    with pytest.raises(SystemExit) as exc:
        acc.preflight(args)
    assert needle in str(exc.value)


def test_guard_cmd_only_configured_containers():
    acc.CONTAINERS.update(api="stack-a-api-1")
    acc.guard_cmd(["docker", "exec", "stack-a-api-1", "printenv", "X"])
    for bad in (
        ["docker", "exec", "other-api-1", "true"],
        ["docker", "logs", "--since", "1h", "other-api-1"],
        ["docker", "rm", "stack-a-api-1"],
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
        return resp(self.code)


def test_cleanup_deletes_every_synthetic_account(monkeypatch):
    FakeClient.deleted = []
    acc.ST["acct"] = {r: {"id": f"id-{r}", "password": "pw"} for r in ("a", "b", "admin")}
    acc.ST["acct"]["x"] = {"id": None, "password": "pw"}
    monkeypatch.setattr(acc, "login", lambda role, label=None: (FakeClient(role), resp()))
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
    monkeypatch.setattr(acc, "login", lambda role, label=None: (FakeClient(role, 500), resp()))
    acc.s12_cleanup()
    assert acc.STEPS[0]["status"] == "FAIL" and len(FakeClient.deleted) == 2


def finish_args(tmp_path, *extra):
    args = acc.build_parser().parse_args(["--target", "audit", *acc_args(tmp_path), *extra])
    args.container_prefix = "stack-a-"
    return args


def test_acceptance_report_has_required_fields(tmp_path):
    args = finish_args(tmp_path)
    acc.rec("1", "eins", "PASS", "ok")
    acc.rec("2", "zwei", "SKIP", "grund")
    acc.ST["env"] = "production"
    assert acc.finish(args, dt.datetime.now(dt.UTC)) == 0
    data = json.loads(next((tmp_path / "rep").glob("*.json")).read_text(encoding="utf-8"))
    assert data["target_sha"] == SHA and data["script_version"] == acc.SCRIPT_VERSION
    assert data["kind"] == "acceptance" and data["dry_run"] is False and data["result"] == "PASS"
    assert data["summary"]["PASS"] == 1 and data["summary"]["SKIP"] == 1
    assert data["limitations"] and data["scope"]
    assert any("Tombstone" in item for item in data["limitations"])
    md = next((tmp_path / "rep").glob("*.md")).read_text(encoding="utf-8")
    assert md.startswith("# Acceptance-Bericht")


def test_acceptance_report_fail_gives_exit_1(tmp_path):
    acc.rec("1", "eins", "FAIL", "kaputt")
    assert acc.finish(finish_args(tmp_path), dt.datetime.now(dt.UTC)) == 1


def test_skip_llm_gives_partial_that_the_marker_gate_rejects(tmp_path):
    import report

    acc.rec("1", "eins", "PASS", "ok")
    assert acc.finish(finish_args(tmp_path, "--skip-llm"), dt.datetime.now(dt.UTC)) == 3
    path = next((tmp_path / "rep").glob("*.json"))
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["result"] == "PARTIAL" and data["extra"]["skip_llm"] is True
    ok, reason = report.check_smoke_report(path, "audit", SHA)
    assert not ok and "PASS" in reason


def test_no_pdf_skip_left_in_acceptance():
    text = Path(acc.__file__).read_text(encoding="utf-8")
    assert "pdftotext" not in text and "Fallback-Extraktion" not in text
    assert "evaluate_pdf" in text


# ------------------------------------------------------------------ Smoke


def test_smoke_prod_needs_guards(tmp_path, capsys):
    stack = write_stack(tmp_path, target="prod", project="stack-p")
    base = ["--target", "prod", *smoke_args(tmp_path, stack)]
    assert smoke.main(base) == 2
    assert "--i-am-sure-prod" in capsys.readouterr().err
    assert smoke.main([*base, "--i-am-sure-prod"]) == 2
    assert smoke.main([*base, "--i-am-sure-prod", "--confirm-sha", "deadbeef"]) == 2
    assert "--confirm-sha" in capsys.readouterr().err


def test_smoke_has_no_default_target(tmp_path):
    with pytest.raises(SystemExit):
        smoke.main(smoke_args(tmp_path))


def test_smoke_target_must_match_stack_config(tmp_path, capsys):
    assert smoke.main(["--target", "prod", "--dry-run", *smoke_args(tmp_path)]) == 2
    assert "CONFIG_TARGET=audit" in capsys.readouterr().err
    args = smoke_args(tmp_path, **{"--api-base": "http://127.0.0.1:17800"})
    assert smoke.main(["--target", "audit", *args]) == 2
    assert "READY_URL-Port" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("replace", "needle"),
    [
        (("--api-base", "https://api.example"), "Loopback"),
        (("--origin", "ftp://x"), "Origin"),
        (("--web-base", "http://127.0.0.1:1"), "Port"),
    ],
)
def test_smoke_url_validation(tmp_path, replace, needle, capsys):
    args = smoke_args(tmp_path, **{replace[0]: replace[1]})
    assert smoke.main(["--target", "audit", *args]) == 2
    assert needle in capsys.readouterr().err


def test_smoke_public_base_only_for_prod(tmp_path, capsys):
    args = [*smoke_args(tmp_path), "--public-base", "https://app.example"]
    assert smoke.main(["--target", "audit", *args]) == 2
    assert "nur mit --target prod" in capsys.readouterr().err


def test_smoke_dry_run_prod_touches_nothing(no_side_effects, capsys, tmp_path):
    stack = write_stack(tmp_path, target="prod", project="stack-p")
    args = [*smoke_args(tmp_path, stack), "--public-base", "https://app.example"]
    assert smoke.main(["--target", "prod", "--dry-run", *args]) == 0
    assert no_side_effects == []
    out = capsys.readouterr().out
    assert "DRY-RUN" in out and "HTTP-Requests=0 Docker-Aufrufe=0" in out
    with pytest.raises(RuntimeError):
        smoke.Client("http://127.0.0.1:1").get("/x")


def smoke_cfg(tmp_path):
    cfg = smoke.build_parser().parse_args(["--target", "audit", *smoke_args(tmp_path)])
    smoke.validate(cfg)
    return cfg


def fake_smoke_sh(**answers):
    table = {
        "select 1": (0, "1\n"),
        "ENVIRONMENT": (0, "production\n"),
        "rev-parse": (0, SHA + "\n"),
        "CORS_ALLOWED_ORIGINS": (0, '["https://app.example"]'),
        "EMAIL_BACKEND": (0, "disabled\n"),
    }
    table.update(answers)

    def fake(args, stdin=None, timeout=60):
        for needle, value in table.items():
            if any(needle in a for a in args):
                return value
        return (0, "0\n")

    return fake


@pytest.mark.parametrize(
    ("answers", "needle"),
    [
        ({"ENVIRONMENT": (1, "")}, "ENVIRONMENT"),
        ({"rev-parse": (0, "e" * 40)}, "HEAD"),
        ({"EMAIL_BACKEND": (0, "smtp")}, "EMAIL_BACKEND"),
        ({"EMAIL_BACKEND": (1, "Error: No such container")}, "EMAIL_BACKEND"),
    ],
)
def test_smoke_preflight_refusals(tmp_path, monkeypatch, answers, needle):
    cfg = smoke_cfg(tmp_path)
    monkeypatch.setattr(smoke, "sh", fake_smoke_sh(**answers))
    with pytest.raises(smoke.Refusal) as exc:
        smoke.preflight(cfg)
    assert needle in str(exc.value)


def test_smoke_preflight_ok_reaches_counters(tmp_path, monkeypatch):
    cfg = smoke_cfg(tmp_path)
    monkeypatch.setattr(smoke, "sh", fake_smoke_sh())
    monkeypatch.setattr(smoke, "count", lambda sql: 7)
    smoke.preflight(cfg)
    assert smoke.ST["users_before"] == 7 and smoke.ST["mail_backend"] == "disabled"


def test_smoke_report_fields(tmp_path):
    cfg = smoke_cfg(tmp_path)
    cfg.public_base = None
    smoke.rec("1", "eins", "PASS", "mail=a@b.de")
    assert smoke.finish(cfg, dt.datetime.now(dt.UTC)) == 0
    data = json.loads(
        next((tmp_path / "rep").glob("smoke-audit-*.json")).read_text(encoding="utf-8")
    )
    assert data["target_sha"] == SHA and "a@b.de" not in json.dumps(data)
    assert any("public-base" in item for item in data["limitations"])


# ------------------------------------------------------------------ pypdf-Pin an einer Stelle


def test_pypdf_pinned_once_and_ci_uses_the_requirements_file():
    pin = (REPO / "scripts/acceptance/requirements.txt").read_text(encoding="utf-8").strip()
    assert pin.startswith("pypdf==")
    ci = (REPO / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "scripts/acceptance/requirements.txt" in ci
    assert "pypdf>=" not in ci and pin not in ci


def test_unified_pdf_size_constant_is_used_by_both_scripts():
    for module in (acc, smoke):
        assert "content_checks.MIN_PDF_BYTES" in Path(module.__file__).read_text(encoding="utf-8")


# ---------------------------------------------------------------- D2: Altersbestaetigung bei Registrierung


class RecordingClient:
    """Zeichnet den Registrierungs-Body auf und antwortet mit 422, damit der Abschnitt abbricht."""

    bodies: list = []

    def __init__(self, *args, **kwargs):
        self.jar = {}

    def post(self, path, body=None, **kwargs):
        RecordingClient.bodies.append((path, body))
        return smoke.R(422, b'{"code":"AGE_CONFIRMATION_REQUIRED"}', {}, [])


def test_acceptance_register_sends_age_confirmed(monkeypatch):
    RecordingClient.bodies = []
    monkeypatch.setattr(acc, "Client", RecordingClient)
    acc.ST["acct"].clear()
    acc.register("a", "abcdef")
    path, body = RecordingClient.bodies[0]
    assert path == "/v1/auth/register"
    assert body["age_confirmed"] is True
    assert set(body) == {"email", "password", "age_confirmed"}


def test_smoke_register_sends_age_confirmed(monkeypatch):
    RecordingClient.bodies = []
    monkeypatch.setattr(smoke, "Client", RecordingClient)
    smoke.s2_auth(SimpleNamespace(api_base="http://127.0.0.1:1"))
    path, body = RecordingClient.bodies[0]
    assert path == "/v1/auth/register"
    assert body["age_confirmed"] is True


# ---------------------------------------------------------------- Proxy-Secret (PROXY_SECRET_ENFORCED=true)


def test_proxy_secret_read_from_env_file(tmp_path):
    env_file = tmp_path / "stack.env"
    env_file.write_text("OTHER=1\nINTERNAL_PROXY_SHARED_SECRET='abc123'\n")
    stack = {"ENV_FILE": str(env_file)}
    assert stack_config.proxy_secret(stack) == "abc123"


@pytest.mark.parametrize("content", ["OTHER=1\n", "INTERNAL_PROXY_SHARED_SECRET=\n"])
def test_proxy_secret_missing_or_empty_is_refused(tmp_path, content):
    env_file = tmp_path / "stack.env"
    env_file.write_text(content)
    with pytest.raises(stack_config.StackRefusalError):
        stack_config.proxy_secret({"ENV_FILE": str(env_file)})
    with pytest.raises(stack_config.StackRefusalError):
        stack_config.proxy_secret({})


class HeaderSpy:
    sent: list = []

    def __init__(self, *args, **kwargs):
        pass

    def request(self, method, path, body=None, headers=None):
        HeaderSpy.sent.append(dict(headers or {}))
        raise RuntimeError("stop")

    def close(self):
        pass


@pytest.mark.parametrize("module", [acc, smoke])
def test_proxy_header_only_on_direct_api_clients(monkeypatch, module):
    monkeypatch.setattr(http.client, "HTTPConnection", HeaderSpy)
    monkeypatch.setitem(module.PROXY_SECRET, "v", "s3cret-value")
    HeaderSpy.sent = []
    for prefix in ("", "/api"):
        client = module.Client("http://127.0.0.1:1", prefix=prefix)
        with pytest.raises(RuntimeError):
            client.get("/v1/health/ready")
    direct, via_web = HeaderSpy.sent
    assert direct["X-Numra-Proxy-Auth"] == "s3cret-value"
    assert "X-Numra-Proxy-Auth" not in via_web


@pytest.mark.parametrize("module", [acc, smoke])
def test_no_proxy_header_without_flag(monkeypatch, module):
    monkeypatch.setattr(http.client, "HTTPConnection", HeaderSpy)
    monkeypatch.setitem(module.PROXY_SECRET, "v", "")
    HeaderSpy.sent = []
    with pytest.raises(RuntimeError):
        module.Client("http://127.0.0.1:1").get("/v1/health/ready")
    assert "X-Numra-Proxy-Auth" not in HeaderSpy.sent[0]
