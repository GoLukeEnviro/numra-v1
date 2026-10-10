#!/usr/bin/env python3
# ruff: noqa: E501, E701, E702, E731
"""NUMRA Smoke-Test (minimal, Standardbibliothek plus pypdf, gibt nie Secrets aus).

Legt GENAU EIN synthetisches Konto <SYNTH_PREFIX><zufall>@<SYNTH_DOMAIN> an, prueft die Kernpfade
(Auth, CSRF, Origin, Proxy, Report+PDF inkl. Inhaltspruefung, DB-Zaehler) und loescht das Konto
am Ende IMMER per POST /v1/account/delete-all. Das Ziel (`--target audit|prod`) hat keinen Default;
gegen prod braucht der Lauf zusaetzlich `--i-am-sure-prod` und `--confirm-sha` (erste 8 Zeichen
von `--target-sha`). Es wird nur SELECT gegen die Datenbank ausgefuehrt. `--stack-config` ist dieselbe
Datei wie fuer numra-release.sh (CONFIG_TARGET == --target, Container `<PROJECT>-<dienst>-1`,
--api-base == READY_URL-Port); `--repo-dir`: Checkout-HEAD muss --target-sha sein.

Aufruf:
    pip install -r scripts/acceptance/requirements.txt
    python3 scripts/acceptance/numra_smoke.py --target audit|prod --target-sha <SHA> \
        --api-base http://127.0.0.1:<API-PORT> --web-base http://127.0.0.1:<WEB-PORT> \
        --stack-config <release-ziel.env> --repo-dir <CHECKOUT> --origin <ERLAUBTE-ORIGIN> \
        --expect-checkins 401|503 \
        --report-dir <DIR> [--public-base https://<HOST>] [--i-am-sure-prod --confirm-sha <SHA8>] \
        [--dry-run]

--expect-checkins: 401 = Flag `checkins` an, 503 = aus (Probe GET /v1/workspaces/<0-uuid>/checkins).
--dry-run: nur Konsistenzpruefung + Plan, KEIN HTTP-Request, KEIN Docker-Aufruf, kein Bericht.
Exitcodes: 0 alles PASS, 1 mindestens ein FAIL, 2 Verweigerung/Preflight/Aufrufpruefung.
"""

import argparse
import datetime as dt
import http.client
import json
import re
import secrets
import ssl
import subprocess
import sys
import time
import urllib.parse
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ops_report"))

import content_checks  # noqa: E402
import report as ops_report  # noqa: E402
import stack_config  # noqa: E402

SCRIPT_VERSION = "2.0.0"
SYNTH_PREFIX = "numra-smoke-"
SYNTH_DOMAIN = "example.com"
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
REPORT_BAD_PATTERNS = content_checks.PLACEHOLDERS + content_checks.SCAFFOLDING
UA = "numra-smoke/2.0"


SECRETS = set()
LOCK = {"on": False}
COUNTERS = {"http": 0, "docker": 0}
STEPS = []
ST = {
    "uid": None,
    "email": None,
    "pw": None,
    "main": None,
    "env": "unknown",
    "users_before": None,
    "failed_before": None,
    "cfg": None,
}


class Refusal(Exception):
    pass


# ------------------------------------------------------------------ Ausgabe / Ergebnisse


def san(s, n=240):
    return ops_report.redact(s, tuple(SECRETS), SYNTH_PREFIX, n)


def rec(sid, name, status, ev=""):
    STEPS.append({"id": sid, "name": name, "status": status, "evidence": san(ev, 260)})
    print(f"STEP {sid:6} {status:5} | {name} | {san(ev, 170)}", flush=True)


def check(sid, name, cond, ev=""):
    rec(sid, name, "PASS" if cond else "FAIL", ev)
    return bool(cond)


def info(sid, name, ev):
    rec(sid, name, "INFO", ev)


def skip(sid, name, why):
    rec(sid, name, "SKIP", why)


def guarded(label):
    def deco(fn):
        def wrap(*a, **k):
            try:
                return fn(*a, **k)
            except Refusal:
                raise
            except Exception as e:
                rec(label, f"Schritt {label} Ausnahme", "FAIL", f"{type(e).__name__}: {e}")
                return None

        wrap.__name__ = fn.__name__
        return wrap

    return deco


# ------------------------------------------------------------------ Konfiguration / Konsistenz


def parse_base(url):
    u = urllib.parse.urlparse(url)
    if u.path not in ("", "/") or u.query or u.params or u.fragment or u.username or u.password:
        raise Refusal(f"Basis-URL mit Pfad/Query/Credentials nicht erlaubt: {url}")
    return u.scheme, u.hostname, u.port or (443 if u.scheme == "https" else 80)


def validate(args):
    """Konsistenz von Ziel, URLs, Containern, Origin und Schutzschaltern. Wirft Refusal."""
    if not re.fullmatch(r"[0-9a-f]{40}", args.target_sha):
        raise Refusal("--target-sha muss eine vollstaendige SHA (40 Hex) sein")
    if args.target == "prod" and not args.dry_run:
        if not args.i_am_sure_prod:
            raise Refusal("Lauf gegen --target prod verweigert: --i-am-sure-prod fehlt")
        if args.confirm_sha != args.target_sha[:8]:
            raise Refusal("--confirm-sha muss den ersten 8 Zeichen von --target-sha entsprechen")
    for label, url in (("--api-base", args.api_base), ("--web-base", args.web_base)):
        sch, host, _port = parse_base(url)
        if sch != "http" or host not in ("127.0.0.1", "localhost"):
            raise Refusal(f"{label}={url} muss eine http-Loopback-URL sein")
    if parse_base(args.api_base)[2] == parse_base(args.web_base)[2]:
        raise Refusal("--api-base und --web-base duerfen nicht denselben Port haben")
    o = urllib.parse.urlparse(args.origin)
    if o.scheme not in ("http", "https") or not o.hostname or o.path not in ("", "/") or o.query:
        raise Refusal(f"--origin ist keine gueltige Origin: {args.origin}")
    origin = f"{o.scheme}://{o.netloc}"
    if args.public_base:
        if args.target != "prod":
            raise Refusal("--public-base nur mit --target prod erlaubt")
        sch, host, _port = parse_base(args.public_base)
        if sch != "https" or host != o.hostname:
            raise Refusal("--public-base muss https sein und denselben Host wie --origin haben")
    args.origin = origin
    args.public_base = args.public_base.rstrip("/") if args.public_base else None
    args.api_base, args.web_base = args.api_base.rstrip("/"), args.web_base.rstrip("/")
    try:
        args.container_prefix = stack_config.bind(
            args.target, args.api_base, stack_config.load(args.stack_config)
        )
    except stack_config.StackRefusalError as exc:
        raise Refusal(str(exc)) from exc
    args.pg_container = f"{args.container_prefix}postgres-1"
    args.api_container = f"{args.container_prefix}api-1"


PLAN = [
    ("1", "Readiness /v1/health/ready 200 healthy"),
    ("2", "Register / Login / me / sessions (ein synthetisches Konto)"),
    ("3", "Logout, danach me 401"),
    ("4", "CSRF: ohne Token 403, ungueltig 403, gueltig 2xx"),
    ("5", "Admin-Route /v1/admin/flags als User 403"),
    (
        "6",
        "Flag-Gating Probe /v1/workspaces/<0-uuid>/checkins (401|503, erwartet --expect-checkins)",
    ),
    (
        "7",
        "IDOR/Consent-Schutz: unbekannte Workspace-/Connection-/Objekt-IDs -> 404 (503 bei Flag aus)",
    ),
    ("8", "Origin-Guard: fremde Origin 403 ORIGIN_NOT_ALLOWED, erlaubte Origin nicht 403"),
    ("9", "Web-Proxy (web-base, optional public-base): Login, Cookies, CSRF"),
    (
        "10",
        "Report-Pfad: Person+Berechnung, QUICK-Report (1 echter LLM-Aufruf), Muster, PDF, llm_generations",
    ),
    ("11", "Queue-/Fehlerstatus: keine QUEUED > 2 min, keine FAILED-Jobs des Smoke-Kontos"),
    ("12", "Cleanup: delete-all, Login 401, User-Zaehler == vorher (finally, immer)"),
]


def print_plan(args):
    print(f"== NUMRA Smoke target={args.target} sha={args.target_sha[:8]} dry_run={args.dry_run}")
    print(
        f"   api={args.api_base} web={args.web_base} public={args.public_base or '-'} origin={args.origin}"
    )
    print(
        f"   pg={args.pg_container} api_container={args.api_container} expect_checkins={args.expect_checkins}"
    )
    print("   Konsistenzpruefung Target/Ports/Container/Origin: OK")
    for sid, txt in PLAN:
        print(f"   Plan {sid:3} {txt}")


# ------------------------------------------------------------------ Docker / DB (nur Zaehler)


def sh(args, stdin=None, timeout=60):
    if LOCK["on"]:
        raise RuntimeError("Docker im Dry-Run gesperrt")
    cfg = ST["cfg"]
    if args[:1] == ["git"]:
        if args[1:2] != ["-C"] or "rev-parse" not in args:
            raise Refusal("von git nur rev-parse erlaubt")
        COUNTERS["docker"] += 1
        p = subprocess.run(args, input=stdin, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    if not (
        len(args) >= 4
        and args[:2] == ["docker", "exec"]
        or (len(args) >= 5 and args[:3] == ["docker", "exec", "-i"])
    ):
        raise Refusal("nur docker exec erlaubt")
    cname = args[3] if args[2] == "-i" else args[2]
    if cname not in (cfg.pg_container, cfg.api_container):
        raise Refusal("Docker-Kommando auf unerlaubten Container")
    COUNTERS["docker"] += 1
    p = subprocess.run(args, input=stdin, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def psql(sql):
    if not re.fullmatch(r"[\w\s'%@.\-,()=<>*:|+]+", sql):
        raise Refusal("unerwartetes Zeichen im SQL")
    if not re.match(r"\s*select\s", sql, re.I):
        raise Refusal("nur SELECT erlaubt")
    cfg = ST["cfg"]
    rc, out = sh(
        [
            "docker",
            "exec",
            cfg.pg_container,
            "psql",
            "-U",
            cfg.pg_user,
            "-d",
            cfg.pg_db,
            "-At",
            "-F",
            "|",
            "-c",
            sql,
        ]
    )
    if rc != 0:
        raise RuntimeError("psql: " + san(out, 160))
    return out.strip()


def need_uuid(v):
    if not UUID_RE.match(str(v)):
        raise Refusal("keine UUID")
    return v


def count(sql):
    return int(psql(sql) or 0)


# ------------------------------------------------------------------ HTTP-Client


class R:
    def __init__(self, code, raw, headers, set_cookies):
        self.code, self.raw, self.headers, self.set_cookies = code, raw, headers, set_cookies
        self.json = None
        if raw and "json" in (headers.get("Content-Type") or ""):
            try:
                self.json = json.loads(raw)
            except Exception:
                self.json = None

    @property
    def err(self):
        return self.json.get("code") if isinstance(self.json, dict) else None

    def short(self):
        return f"{self.code}" + (f" {self.err}" if self.err else "")


LOGIN_TIMES = []


def login_gate():
    now = time.time()
    while LOGIN_TIMES and now - LOGIN_TIMES[0] > 60:
        LOGIN_TIMES.pop(0)
    if len(LOGIN_TIMES) >= 6:
        time.sleep(max(1, 61 - (now - LOGIN_TIMES[0])))
    LOGIN_TIMES.append(time.time())


class Client:
    def __init__(self, base, prefix=""):
        sch, host, port = parse_base(base)
        self.scheme, self.host, self.port, self.prefix = sch, host, port, prefix
        self.jar = {}

    def req(self, method, path, body=None, headers=None, csrf=True, timeout=60, use_cookies=True):
        if LOCK["on"]:
            raise RuntimeError("HTTP im Dry-Run gesperrt")
        h = {"Accept": "application/json", "User-Agent": UA}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        if use_cookies and self.jar:
            h["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.jar.items())
        if csrf is True and "numra_csrf" in self.jar:
            h["x-csrf-token"] = self.jar["numra_csrf"]
        elif isinstance(csrf, str):
            h["x-csrf-token"] = csrf
        h.update(headers or {})
        if self.scheme == "https":
            c = http.client.HTTPSConnection(
                self.host, self.port, timeout=timeout, context=ssl.create_default_context()
            )
        else:
            c = http.client.HTTPConnection(self.host, self.port, timeout=timeout)
        COUNTERS["http"] += 1
        try:
            c.request(method, self.prefix + path, body=data, headers=h)
            resp = c.getresponse()
            raw = resp.read()
            sc = resp.msg.get_all("Set-Cookie") or []
            r = R(resp.status, raw, resp.msg, sc)
        finally:
            c.close()
        for ck in sc:
            kv = ck.partition(";")[0]
            k, _, v = kv.partition("=")
            low = ck.lower()
            if "max-age=0" in low or v == "" or "expires=thu, 01 jan 1970" in low:
                self.jar.pop(k.strip(), None)
            else:
                self.jar[k.strip()] = v
                SECRETS.add(v)
        return r

    def get(self, p, **k):
        return self.req("GET", p, **k)

    def post(self, p, body=None, **k):
        return self.req("POST", p, body if body is not None else {}, **k)


def cookie_attrs(set_cookie):
    parts = [p.strip() for p in set_cookie.split(";")]
    low = [p.lower() for p in parts[1:]]
    return parts[0].split("=")[0], {
        "httponly": "httponly" in low,
        "secure": "secure" in low,
        "samesite": next((p.split("=")[1] for p in low if p.startswith("samesite=")), None),
        "path": next((p.split("=")[1] for p in low if p.startswith("path=")), None),
    }


def flatten_strings(o, out=None):
    out = [] if out is None else out
    if isinstance(o, str):
        out.append(o)
    elif isinstance(o, dict):
        for v in o.values():
            flatten_strings(v, out)
    elif isinstance(o, list):
        for v in o:
            flatten_strings(v, out)
    return out


def new_login_client(base, prefix="", headers=None):
    c = Client(base, prefix)
    login_gate()
    r = c.post(
        "/v1/auth/login", {"email": ST["email"], "password": ST["pw"]}, csrf=False, headers=headers
    )
    return c, r


def ensure_main():
    """Liefert einen Client mit gueltiger Session des Smoke-Kontos (loggt bei Bedarf neu ein)."""
    m = ST["main"]
    if m is not None and m.get("/v1/auth/me").code == 200:
        return m
    m, r = new_login_client(ST["cfg"].api_base)
    ST["main"] = m if r.code == 200 else None
    return ST["main"]


# ------------------------------------------------------------------ Preflight


def preflight(cfg):
    ST["cfg"] = cfg
    rc, out = sh(
        [
            "docker",
            "exec",
            cfg.pg_container,
            "psql",
            "-U",
            cfg.pg_user,
            "-d",
            cfg.pg_db,
            "-At",
            "-c",
            "select 1",
        ]
    )
    if rc != 0 or out.strip() != "1":
        raise Refusal("Preflight: DB-Zugriff (select 1) fehlgeschlagen: " + san(out, 120))
    rc, out = sh(["docker", "exec", cfg.api_container, "printenv", "ENVIRONMENT"])
    if rc != 0 or not out.strip():
        raise Refusal("Preflight: ENVIRONMENT im API-Container nicht lesbar (falscher Stack?)")
    ST["env"] = out.strip()
    rc, out = sh(["git", "-C", cfg.repo_dir, "rev-parse", "HEAD"])
    if rc != 0 or out.strip() != cfg.target_sha:
        raise Refusal("Preflight: Checkout-HEAD != --target-sha")
    rc, out = sh(["docker", "exec", cfg.api_container, "printenv", "CORS_ALLOWED_ORIGINS"])
    try:
        cors = json.loads(out) if rc == 0 else []
    except Exception:
        cors = [x.strip() for x in out.split(",")]
    if cfg.origin not in cors:
        raise Refusal("Preflight: --origin steht nicht in CORS_ALLOWED_ORIGINS des API-Containers")
    rc, out = sh(["docker", "exec", cfg.api_container, "printenv", "EMAIL_BACKEND"])
    try:
        ST["mail_backend"] = stack_config.check_mail_backend(
            out if rc == 0 else "", cfg.allow_smtp_synthetic
        )
    except stack_config.StackRefusalError as exc:
        raise Refusal(f"Preflight: {exc}") from exc
    ST["users_before"] = count("select count(*) from users where deleted_at is null")
    ST["failed_before"] = count(
        "select (select count(*) from report_jobs where status='FAILED') + (select count(*) from analysis_jobs where status='FAILED')"
    )
    print(
        f"== Preflight OK env={ST['env']} aktive_user_vorher={ST['users_before']} mailfrei=verifiziert",
        flush=True,
    )


# ------------------------------------------------------------------ Schritte


@guarded("1")
def s1_ready(cfg):
    r = Client(cfg.api_base).get("/v1/health/ready")
    check(
        "1",
        "Readiness /v1/health/ready 200 healthy",
        r.code == 200
        and isinstance(r.json, dict)
        and r.json
        and all(v == "healthy" for v in r.json.values()),
        f"{r.code} {r.json}",
    )


@guarded("2")
def s2_auth(cfg):
    rand = secrets.token_hex(4)
    ST["email"] = f"{SYNTH_PREFIX}{rand}@{SYNTH_DOMAIN}"
    ST["pw"] = secrets.token_urlsafe(18) + "Aa1!"
    SECRETS.add(ST["pw"])
    R0 = Client(cfg.api_base)
    r = R0.post("/v1/auth/register", {"email": ST["email"], "password": ST["pw"]}, csrf=False)
    ok = r.code == 201 and isinstance(r.json, dict) and UUID_RE.match(str(r.json.get("id", "")))
    check(
        "2.1",
        "Registrierung -> 201, Session+CSRF-Cookie",
        ok and "numra_session" in R0.jar and "numra_csrf" in R0.jar,
        r.short(),
    )
    if not ok:
        return
    ST["uid"] = r.json["id"]
    ST["main"] = R0
    cks = dict(cookie_attrs(c) for c in r.set_cookies)
    s, c = cks.get("numra_session"), cks.get("numra_csrf")
    want_secure = ST["env"] == "production"
    check(
        "2.2",
        f"Cookie-Flags (Session HttpOnly+lax, CSRF lesbar, Secure={want_secure} passend zu ENVIRONMENT={ST['env']})",
        bool(s and c)
        and s["httponly"]
        and s["samesite"] == "lax"
        and not c["httponly"]
        and s["secure"] == want_secure
        and c["secure"] == want_secure,
        f"session={s} csrf={c}",
    )
    L, lr = new_login_client(cfg.api_base)
    check(
        "2.3",
        "Login (zweite Session) -> 200",
        lr.code == 200 and lr.json.get("email") == ST["email"],
        lr.short(),
    )
    ST["login_client"] = L
    me = L.get("/v1/auth/me")
    check(
        "2.4",
        "me -> eigene Daten, Rolle USER, aktiv",
        me.code == 200
        and me.json["email"] == ST["email"]
        and str(me.json["role"]).endswith("USER")
        and me.json["is_active"],
        me.short(),
    )
    ss = R0.get("/v1/auth/sessions")
    cur = [x for x in (ss.json or []) if x.get("is_current")] if ss.code == 200 else []
    check(
        "2.5",
        "sessions: >=2 aktiv, genau eine is_current",
        ss.code == 200 and len(ss.json) >= 2 and len(cur) == 1,
        f"{ss.code} n={len(ss.json or [])} cur={len(cur)}",
    )


@guarded("3")
def s3_logout(cfg):
    L = ST.get("login_client")
    if not L:
        return skip("3", "Logout", "kein Login-Client")
    stale = dict(L.jar)
    r = L.post("/v1/auth/logout")
    old = Client(cfg.api_base)
    old.jar = stale
    after = old.get("/v1/auth/me")
    main_ok = ST["main"].get("/v1/auth/me").code == 200
    check(
        "3",
        "Logout -> 204, alte Session danach me 401, andere Session unberuehrt",
        r.code == 204 and after.code == 401 and main_ok,
        f"logout={r.code} me_after={after.code} other_session_ok={main_ok}",
    )


@guarded("4")
def s4_csrf(cfg):
    M, ep = ensure_main(), "/v1/auth/sessions/revoke-others"
    r1 = M.post(ep, csrf=False)
    check(
        "4.1",
        "mutierend ohne x-csrf-token -> 403 CSRF_VALIDATION_FAILED",
        r1.code == 403 and r1.err == "CSRF_VALIDATION_FAILED",
        r1.short(),
    )
    r2 = M.post(ep, csrf="ungueltig-" + secrets.token_hex(8))
    check("4.2", "ungueltiger Token -> 403", r2.code == 403, r2.short())
    r3 = M.post(ep)
    check("4.3", "gueltiger Token -> 2xx", 200 <= r3.code < 300, r3.short())


@guarded("5")
def s5_admin(cfg):
    M = ensure_main()
    r = M.get("/v1/admin/flags")
    a = Client(cfg.api_base).get("/v1/admin/flags")
    check(
        "5",
        "Admin-Route /v1/admin/flags als User -> 403 (ohne Session 401)",
        r.code == 403 and a.code == 401,
        f"user={r.short()} anon={a.short()}",
    )


@guarded("6")
def s6_flag(cfg):
    r = Client(cfg.api_base).get(f"/v1/workspaces/{'0' * 8}-0000-0000-0000-{'0' * 12}/checkins")
    desc = {401: "Flag checkins AN", 503: "Flag checkins AUS"}.get(r.code, "unerwartet")
    check(
        "6.1",
        "Probe checkins liefert 401 oder 503",
        r.code in (401, 503),
        f"code={r.code} ({desc})",
    )
    check(
        "6.2",
        f"Probe entspricht --expect-checkins {cfg.expect_checkins}",
        r.code == cfg.expect_checkins,
        f"got={r.code} expected={cfg.expect_checkins}",
    )


@guarded("7")
def s7_idor(cfg):
    M = ensure_main()
    u = lambda: str(uuid.uuid4())
    w = u()
    gets = {
        "ws": f"/v1/workspaces/{w}",
        "ws_consent": f"/v1/workspaces/{w}/consent",
        "ws_analysis": f"/v1/workspaces/{w}/relationship-analysis",
        "ws_shadow": f"/v1/workspaces/{w}/shadow-dynamics",
        "ws_tasks": f"/v1/workspaces/{w}/tasks",
        "ws_checkins": f"/v1/workspaces/{w}/checkins/current",
        "analysis_job": f"/v1/analysis-jobs/{u()}",
        "person": f"/v1/people/{u()}",
        "person_calcs": f"/v1/people/{u()}/calculations",
        "person_notes": f"/v1/people/{u()}/private-notes",
        "calc": f"/v1/calculations/{u()}",
        "report": f"/v1/reports/{u()}",
        "report_job": f"/v1/report-jobs/{u()}",
        "export_dl": f"/v1/exports/{u()}/download",
    }
    obs = {k: M.get(p).code for k, p in gets.items()}
    obs["grant"] = M.post(f"/v1/workspaces/{u()}/consent/grant", {"scope": "CORE_NUMEROLOGY"}).code
    obs["revoke"] = M.post(
        f"/v1/workspaces/{u()}/consent/revoke", {"scope": "CORE_NUMEROLOGY"}
    ).code
    obs["dissolve"] = M.post(f"/v1/connections/{u()}/dissolve").code
    n404 = sum(v == 404 for v in obs.values())
    check(
        "7",
        "unbekannte IDs -> 404 (503 nur bei Flag aus), mind. 10 mal 404",
        all(v in (404, 503) for v in obs.values()) and n404 >= 10,
        f"404={n404}/{len(obs)} {obs}",
    )


@guarded("8")
def s8_origin(cfg):
    M, ep = ensure_main(), "/v1/auth/sessions/revoke-others"
    bad = M.post(ep, headers={"Origin": "https://evil.example"})
    check(
        "8.1",
        "fremde Origin (gueltiger Token) -> 403 ORIGIN_NOT_ALLOWED",
        bad.code == 403 and bad.err == "ORIGIN_NOT_ALLOWED",
        bad.short(),
    )
    ok = M.post(ep, headers={"Origin": cfg.origin})
    check(
        "8.2",
        "erlaubte Origin -> nicht 403 (erwartet 2xx)",
        ok.code != 403 and 200 <= ok.code < 300,
        ok.short(),
    )


def proxy_checks(label, base, cfg):
    sid = "9" + label[0]
    P = Client(base, prefix="/api")
    hdr = {"Origin": cfg.origin}
    login_gate()
    r = P.post(
        "/v1/auth/login", {"email": ST["email"], "password": ST["pw"]}, csrf=False, headers=hdr
    )
    check(
        f"{sid}.1",
        f"[{label}] Login ueber /api/v1/auth/login -> 200",
        r.code == 200 and isinstance(r.json, dict) and r.json.get("email") == ST["email"],
        r.short(),
    )
    if r.code != 200:
        return
    cks = dict(cookie_attrs(c) for c in r.set_cookies)
    s, c = cks.get("numra_session"), cks.get("numra_csrf")
    check(
        f"{sid}.2",
        f"[{label}] Set-Cookie weitergereicht (numra_session HttpOnly, numra_csrf lesbar)",
        bool(s and c) and s["httponly"] and not c["httponly"],
        f"cookies={sorted(cks)}",
    )
    info(
        f"{sid}.2s",
        f"[{label}] Secure/SameSite",
        f"session.secure={s and s['secure']} csrf.secure={c and c['secure']} samesite={s and s['samesite']}",
    )
    check(f"{sid}.3", f"[{label}] me ueber Proxy -> 200", P.get("/v1/auth/me").code == 200)
    ep = "/v1/auth/sessions/revoke-others"
    a = P.post(ep, csrf=False, headers=hdr)
    b = P.post(ep, csrf="ungueltig-" + secrets.token_hex(8), headers=hdr)
    d = P.post(ep, headers=hdr)
    check(
        f"{sid}.4",
        f"[{label}] CSRF: ohne Token 403 CSRF_VALIDATION_FAILED, ungueltig 403, gueltig 2xx",
        a.code == 403
        and a.err == "CSRF_VALIDATION_FAILED"
        and b.code == 403
        and 200 <= d.code < 300,
        f"{a.short()} / {b.short()} / {d.short()}",
    )
    stale = dict(P.jar)
    lo = P.post("/v1/auth/logout", headers=hdr)
    old = Client(base, prefix="/api")
    old.jar = stale
    check(
        f"{sid}.5",
        f"[{label}] Logout ueber Proxy 204, alte Session danach 401",
        lo.code == 204 and old.get("/v1/auth/me").code == 401,
        f"logout={lo.code}",
    )


@guarded("9")
def s9_proxy(cfg):
    proxy_checks("web", cfg.web_base, cfg)
    if cfg.public_base:
        proxy_checks("public", cfg.public_base, cfg)
    else:
        skip("9p", "Proxy ueber public-base", "--public-base nicht gesetzt")


def poll_job(M, path, timeout):
    t0 = time.time()
    last = {}
    while time.time() - t0 < timeout:
        r = M.get(path)
        if r.code == 200:
            last = r.json
            if last["status"] in ("COMPLETE", "FAILED", "CANCELLED"):
                return last, int(time.time() - t0)
        time.sleep(8)
    return dict(last, status=last.get("status", "TIMEOUT"), timeout=True), int(time.time() - t0)


@guarded("10")
def s10_report(cfg):
    M = ensure_main()
    if not M:
        return skip("10", "Report-Pfad", "keine Session")
    today = dt.date.today().isoformat()
    p = M.post(
        "/v1/people",
        {
            "birth_first_names": "Smoke",
            "birth_last_name": "Probe",
            "birth_date": "1990-03-14",
            "preferred_name": "Smoke",
        },
    )
    c = (
        M.post(f"/v1/people/{p.json['id']}/calculations", {"as_of_date": today})
        if p.code == 201
        else p
    )
    if not check(
        "10.1",
        "Person + Berechnung anlegen -> 201/201",
        p.code == 201 and c.code == 201,
        f"{p.short()} / {c.short()}",
    ):
        return
    r = M.post("/v1/reports", {"calculation_id": c.json["id"], "report_type": "QUICK"})
    if not check("10.2", "QUICK-Report-Job erzeugen -> 201", r.code == 201, r.short()):
        return
    rid, jid = r.json["id"], need_uuid(r.json["job_id"])
    ST["report_job"] = jid
    job, dur = poll_job(M, f"/v1/report-jobs/{jid}", cfg.llm_timeout)
    if not check(
        "10.3",
        f"Report-Job COMPLETE (Timeout {cfg.llm_timeout}s)",
        job.get("status") == "COMPLETE",
        f"status={job.get('status')} err={job.get('error_code')} dauer={dur}s",
    ):
        return
    rep = M.get(f"/v1/reports/{rid}")
    content = rep.json.get("content") if rep.code == 200 and isinstance(rep.json, dict) else None
    strs = flatten_strings(content)
    chars = sum(len(s) for s in strs)
    check(
        "10.4",
        "Report-Inhalt lesbar (content vorhanden, >=300 Zeichen)",
        bool(content) and chars >= 300,
        f"{rep.code} chars={chars}",
    )
    hits = {}
    for pat in REPORT_BAD_PATTERNS:
        n = sum(len(re.findall(pat, s)) for s in strs)
        if n:
            hits[pat] = n
    check(
        "10.5",
        "Report-Text ohne Platzhalter/Scaffolding-Muster",
        not hits and chars > 0,
        f"treffer={hits or 'keine'}",
    )
    ex = M.post("/v1/exports", {"report_id": rid, "export_type": "pdf"}, timeout=180)
    if not check("10.6", "PDF-Export erzeugen -> 201", ex.code == 201, ex.short()):
        return
    eid, cur = ex.json["id"], []
    for _ in range(40):
        cur = [e for e in (M.get("/v1/exports").json or []) if e["id"] == eid]
        if cur and cur[0]["status"] in ("complete", "failed"):
            break
        time.sleep(4)
    check(
        "10.7",
        "Export-Status complete",
        bool(cur) and cur[0]["status"] == "complete",
        f"status={cur and cur[0]['status']} err={cur and cur[0].get('error_code')}",
    )
    d = M.get(f"/v1/exports/{eid}/download", timeout=120)
    pdf = d.raw or b""
    check(
        "10.8",
        "PDF: 200, application/pdf, %PDF, %%EOF, > 20 KB",
        d.code == 200
        and "pdf" in (d.headers.get("Content-Type") or "")
        and pdf[:4] == b"%PDF"
        and b"%%EOF" in pdf[-2048:]
        and len(pdf) > content_checks.MIN_PDF_BYTES,
        f"{d.code} bytes={len(pdf)} ct={d.headers.get('Content-Type')}",
    )
    for suffix, name, passed, evidence in content_checks.evaluate_pdf(
        content_checks.analyze_pdf(pdf)
    ):
        check(f"10.8-{suffix}", name, passed, evidence)
    row = psql(
        "select count(*), count(*) filter (where status='ok'), coalesce(sum(total_tokens),0), count(total_tokens), count(latency_ms) "
        f"from llm_generations where source='report' and report_job_id='{jid}'"
    )
    n, ok_n, tok, tok_set, lat = [int(x or 0) for x in (row.split("|") + ["0"] * 5)[:5]]
    check(
        "10.9",
        "llm_generations: Zeilen > 0 und status ok",
        n > 0 and ok_n > 0,
        f"rows={n} ok={ok_n}",
    )
    if tok_set == 0:
        info(
            "10.10",
            "llm_generations total_tokens",
            "alle NULL (Provider meldet keine Usage oder Erfassung fehlt)",
        )
    else:
        check(
            "10.10",
            "llm_generations total_tokens > 0",
            tok > 0,
            f"summe={tok} gesetzt={tok_set}/{n}",
        )
    check("10.11", "llm_generations Latenz gefuellt", n > 0 and lat == n, f"gesetzt={lat}/{n}")


@guarded("11")
def s11_queue(cfg):
    q = {
        t: count(
            f"select count(*) from {t} where status='QUEUED' and created_at < now() - interval '2 minutes'"
        )
        for t in ("analysis_jobs", "report_jobs")
    }
    check("11.1", "keine QUEUED-Jobs aelter 2 min (global, Zaehler)", sum(q.values()) == 0, str(q))
    uid = need_uuid(ST["uid"]) if ST["uid"] else None
    if uid:
        f = {
            "report_jobs": count(
                f"select count(*) from report_jobs where status='FAILED' and user_id='{uid}'"
            ),
            "analysis_jobs": count(
                f"select count(*) from analysis_jobs where status='FAILED' and requested_by_user_id='{uid}'"
            ),
        }
        check("11.2", "keine FAILED-Jobs des Smoke-Kontos", sum(f.values()) == 0, str(f))
    now_failed = count(
        "select (select count(*) from report_jobs where status='FAILED') + (select count(*) from analysis_jobs where status='FAILED')"
    )
    info(
        "11.3",
        "FAILED-Jobs global (Delta seit Start; Fremdlast moeglich)",
        f"vorher={ST['failed_before']} jetzt={now_failed}",
    )


def s12_cleanup(cfg):
    uid = ST["uid"]
    if not uid:
        return skip("12", "Cleanup", "kein Konto angelegt")
    uid = need_uuid(uid)
    ok = False
    for _ in (1, 2):
        try:
            M = ensure_main()
            if M is None:
                continue
            r = M.post("/v1/account/delete-all", {"password": ST["pw"]})
            ok = r.code == 204
            if ok:
                break
            last = r.short()
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
    check("12.1", "delete-all fuer Smoke-Konto -> 204", ok, "" if ok else last)
    if not ok:
        print(
            f"!! MANUELLE BEREINIGUNG NOETIG: Smoke-Konto id={uid[:8]}.. nicht geloescht",
            flush=True,
        )
        return
    try:
        login_gate()
        lr = Client(cfg.api_base).post(
            "/v1/auth/login", {"email": ST["email"], "password": ST["pw"]}, csrf=False
        )
        check("12.2", "Login mit Smoke-Zugangsdaten danach -> 401", lr.code == 401, lr.short())
        after = count("select count(*) from users where deleted_at is null")
        check(
            "12.3",
            "aktive User-Zaehler == Zaehler vor dem Test",
            after == ST["users_before"],
            f"vorher={ST['users_before']} nachher={after}",
        )
        row = psql(f"select is_active, deleted_at is not null from users where id='{uid}'")
        check(
            "12.4",
            "Smoke-User-Zeile entwertet (is_active=f, deleted_at gesetzt, E-Mail anonymisiert)",
            row == "f|t",
            row,
        )
        left = {
            "people": count(f"select count(*) from people where user_id='{uid}'"),
            "report_jobs": count(f"select count(*) from report_jobs where user_id='{uid}'"),
        }
        check(
            "12.5",
            "keine Nutzdaten des Smoke-Kontos uebrig (people/report_jobs)",
            sum(left.values()) == 0,
            str(left),
        )
        tot = count("select count(*) from users")
        info(
            "12.6",
            "Hinweis",
            f"delete-all laesst anonymisierte Tombstone-Zeile (users gesamt jetzt {tot}); aktive Zaehler siehe 12.3",
        )
    except Exception as e:
        rec("12.x", "Cleanup-Verifikation Ausnahme", "FAIL", f"{type(e).__name__}: {e}")


# ------------------------------------------------------------------ Main

LIMITATIONS = [
    "Legt genau ein synthetisches Konto an und loescht es per delete-all; Tombstone-Zeile in users bleibt (Zaehler: aktive User).",
    "Ein echter LLM-Aufruf (QUICK-Report) pro Lauf; LLM-Qualitaet wird nur formal geprueft.",
    "Nur Kernpfade; keine Lastmessung, keine Pruefung der Zwei-Konten-Journey (das leistet numra_acceptance.py auf Audit).",
    "Die Evidenz ist redigiert (keine Secrets, Mails, UUID-Reste).",
]


def finish(cfg, t0):
    limitations = list(LIMITATIONS)
    if not cfg.public_base:
        limitations.append(
            "Kein Proxy-Test ueber die oeffentliche Domain (--public-base nicht gesetzt)."
        )
    rep = ops_report.build_report(
        kind="smoke",
        target=cfg.target,
        target_sha=cfg.target_sha,
        script="numra_smoke.py",
        script_version=SCRIPT_VERSION,
        started=t0.isoformat(timespec="seconds"),
        finished=ops_report.now_iso(),
        scope=[f"{sid}: {txt}" for sid, txt in PLAN],
        steps=STEPS,
        limitations=limitations,
        extra={
            "environment": ST["env"],
            "http_requests": COUNTERS["http"],
            "docker_calls": COUNTERS["docker"],
            "container_prefix": cfg.container_prefix,
            "mail_backend": ST.get("mail_backend", "unknown"),
        },
    )
    stem = f"smoke-{cfg.target}-{t0.strftime('%Y%m%dT%H%M%SZ')}"
    json_path, md_path = ops_report.write_report(rep, Path(cfg.report_dir), stem)
    s = rep["summary"]
    print(
        f"\nErgebnis {rep['result']}: PASS {s['PASS']} FAIL {s['FAIL']} SKIP {s['SKIP']} INFO {s['INFO']}"
    )
    print(f"HTTP-Requests: {COUNTERS['http']}  Docker-Aufrufe: {COUNTERS['docker']}")
    print(f"Bericht: {md_path}\nBericht: {json_path}")
    return 0 if rep["result"] == "PASS" else 1


def build_parser():
    ap = argparse.ArgumentParser(description="NUMRA Smoke-Test")
    ap.add_argument("--target", required=True, choices=("audit", "prod"))
    ap.add_argument("--target-sha", required=True, help="vollstaendige SHA des geprueften Stands")
    ap.add_argument("--i-am-sure-prod", action="store_true", dest="i_am_sure_prod")
    ap.add_argument("--confirm-sha", default="", help="erste 8 Zeichen von --target-sha (nur prod)")
    ap.add_argument("--api-base", required=True)
    ap.add_argument("--web-base", required=True)
    ap.add_argument("--public-base")
    ap.add_argument("--stack-config", required=True, help="Konfig wie fuer numra-release.sh")
    ap.add_argument("--origin", required=True)
    ap.add_argument("--expect-checkins", type=int, choices=(401, 503), required=True)
    ap.add_argument("--report-dir", required=True)
    ap.add_argument("--repo-dir", required=True, help="Checkout; HEAD muss --target-sha sein")
    ap.add_argument("--allow-smtp-synthetic", action="store_true")
    ap.add_argument("--pg-user", default="numra")
    ap.add_argument("--pg-db", default="numra")
    ap.add_argument("--llm-timeout", type=int, default=600)
    ap.add_argument("--dry-run", action="store_true")
    return ap


def main(argv=None):
    cfg = build_parser().parse_args(argv)
    try:
        content_checks.analyze_pdf(b"")
    except content_checks.MissingDependencyError as e:
        print(f"VERWEIGERT: {e}", file=sys.stderr)
        return 2
    try:
        validate(cfg)
    except Refusal as e:
        print(f"VERWEIGERT: {e}", file=sys.stderr)
        return 2
    print_plan(cfg)
    if cfg.dry_run:
        LOCK["on"] = True
        print(
            f"DRY-RUN: HTTP-Requests={COUNTERS['http']} Docker-Aufrufe={COUNTERS['docker']} (Netz/Docker gesperrt)"
        )
        return 0
    t0 = dt.datetime.now(dt.UTC)
    try:
        preflight(cfg)
    except (Refusal, RuntimeError, subprocess.TimeoutExpired) as e:
        print(f"PREFLIGHT ABGEBROCHEN (nichts angelegt): {e}", file=sys.stderr)
        return 2
    try:
        s1_ready(cfg)
        s2_auth(cfg)
        if ST["uid"]:
            for fn in (
                s3_logout,
                s4_csrf,
                s5_admin,
                s6_flag,
                s7_idor,
                s8_origin,
                s9_proxy,
                s10_report,
                s11_queue,
            ):
                fn(cfg)
        else:
            for sid, txt in PLAN[2:11]:
                skip(sid, txt, "kein Konto")
    finally:
        s12_cleanup(cfg)
    return finish(cfg, t0)


if __name__ == "__main__":
    sys.exit(main())
