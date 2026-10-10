#!/usr/bin/env python3
# ruff: noqa: E501, E701, E702, E731
"""NUMRA-Abnahmelauf fuer einen Audit-Stack (nur Standardbibliothek plus pypdf fuer PDFs).

Fuehrt eine vollstaendige Nutzer-Journey gegen den Audit-Stack aus (Auth, Zwei-Konten-Journey,
Einladungen/Consent/IDOR, Admin-Flags, LLM-Analysen und Report+PDF, Web-Proxy, Worker-Logs) und
schreibt einen Markdown+JSON-Bericht. Der Lauf veraendert die Audit-Datenbank (E-Mail-Verifizierung
per UPDATE, promote-admin, Flag-Umschaltung) und ist deshalb NUR fuer `--target audit`; fuer
Produktion gibt es numra_smoke.py. Es gibt keinen Default fuer das Ziel.

Synthetische Daten tragen immer das Praefix SYNTH_PREFIX und die Domain SYNTH_DOMAIN und werden
am Ende per POST /v1/account/delete-all entfernt (Schritt 12, auch bei Fehlern). Gibt nie
Secrets aus; Zugangsdaten leben nur im Prozessspeicher.

Aufruf:
    pip install -r scripts/acceptance/requirements.txt
    python3 scripts/acceptance/numra_acceptance.py --target audit --target-sha <SHA> \
        --api-base http://127.0.0.1:<API-PORT> --web-base http://127.0.0.1:<WEB-PORT> \
        --stack-config <release-audit.env> --repo-dir <CHECKOUT> --report-dir <DIR> \
        [--skip-llm] [--reset-ratelimit] [--llm-timeout 600] [--allow-smtp-synthetic] [--dry-run]

`--stack-config` ist dieselbe Datei wie fuer numra-release.sh: CONFIG_TARGET muss zu --target passen,
Container heissen `<PROJECT>-<dienst>-1`, --api-base muss auf den READY_URL-Port zeigen. `--repo-dir`
ist Pflicht: der Checkout-HEAD muss --target-sha sein. Mit --skip-llm ist das Ergebnis PARTIAL (nie
als Abnahme fuer den Marker gueltig). Exit 0 = PASS, 1 = mindestens ein FAIL, 2 = Aufruf/Preflight
verweigert, 3 = PARTIAL.
"""

import argparse
import datetime as dt
import http.client
import json
import re
import secrets
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ops_report"))

import content_checks  # noqa: E402
import report as ops_report  # noqa: E402
import stack_config  # noqa: E402

SCRIPT_VERSION = "2.0.0"
SYNTH_PREFIX = "numra-acc-"
SYNTH_DOMAIN = "example.com"
API = ""
WEB = ""
CONTAINERS: dict[str, str] = {}
DRY = {"on": False}
ZERO = "00000000-0000-0000-0000-000000000000"
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
SECRETS = set()  # bekannte Geheimnisse, werden aus jeder Ausgabe entfernt

# ---------------------------------------------------------------- Sicherheit / Helfer


def guard_cmd(args):
    """Docker nur gegen die konfigurierten Container, git nur lesend."""
    if args[:2] in (["docker", "exec"], ["docker", "logs"]):
        if not any(a in CONTAINERS.values() for a in args):
            raise SystemExit("ABBRUCH: Docker-Kommando ohne konfigurierten Container")
    elif args[:1] == ["git"]:
        if "rev-parse" not in args:
            raise SystemExit("ABBRUCH: nur git rev-parse erlaubt")
    else:
        raise SystemExit("ABBRUCH: unerlaubtes Kommando")


def sh(args, stdin=None, timeout=120):
    if DRY["on"]:
        raise RuntimeError("Prozessaufruf im Dry-Run gesperrt")
    guard_cmd(args)
    p = subprocess.run(args, input=stdin, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def san(s, n=220):
    return ops_report.redact(s, tuple(SECRETS), SYNTH_PREFIX, n)


def psql(sql):
    if not re.fullmatch(r"[\w\s'%@.\-,()=<>*:|]+", sql):
        raise SystemExit("ABBRUCH: unerwartetes Zeichen im SQL")
    rc, out = sh(
        [
            "docker",
            "exec",
            CONTAINERS["pg"],
            "psql",
            "-U",
            "numra",
            "-d",
            "numra",
            "-At",
            "-F",
            "|",
            "-c",
            sql,
        ]
    )
    if rc != 0:
        raise RuntimeError("psql: " + san(out))
    return out.strip()


def need_uuid(v):
    if not UUID_RE.match(str(v)):
        raise SystemExit("ABBRUCH: keine UUID")
    return v


# ---------------------------------------------------------------- HTTP-Client


class R:
    def __init__(self, code, raw, headers, set_cookies):
        self.code, self.raw, self.headers, self.set_cookies = code, raw, headers, set_cookies
        try:
            self.json = json.loads(raw) if raw else None
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
    if len(LOGIN_TIMES) >= 8:
        time.sleep(max(1, 61 - (now - LOGIN_TIMES[0])))
    LOGIN_TIMES.append(time.time())


class Client:
    def __init__(self, base, prefix="", label=""):
        u = urllib.parse.urlparse(base)
        if u.scheme != "http" or u.hostname not in ("127.0.0.1", "localhost"):
            raise SystemExit("ABBRUCH: nur http-Loopback-Basis-URLs erlaubt")
        self.host, self.port, self.prefix, self.label = u.hostname, u.port, prefix, label
        self.jar = {}

    def req(self, method, path, body=None, headers=None, csrf=True, timeout=60, use_cookies=True):
        if DRY["on"]:
            raise RuntimeError("HTTP im Dry-Run gesperrt")
        h = {"Accept": "application/json"}
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
        c = http.client.HTTPConnection(self.host, self.port, timeout=timeout)
        try:
            c.request(method, self.prefix + path, body=data, headers=h)
            resp = c.getresponse()
            raw = resp.read()
            sc = resp.msg.get_all("Set-Cookie") or []
            r = R(resp.status, raw, resp.msg, sc)
        finally:
            c.close()
        for ck in sc:
            kv, _, rest = ck.partition(";")
            k, _, v = kv.partition("=")
            if "max-age=0" in ck.lower() or v == "" or "expires=thu, 01 jan 1970" in ck.lower():
                self.jar.pop(k.strip(), None)
            else:
                self.jar[k.strip()] = v
                SECRETS.add(v)
        return r

    def get(self, p, **k):
        return self.req("GET", p, **k)

    def post(self, p, body=None, **k):
        return self.req("POST", p, body if body is not None else {}, **k)

    def patch(self, p, body, **k):
        return self.req("PATCH", p, body, **k)

    def me_id(self):
        r = self.get("/v1/auth/me")
        return r.json["id"] if r.code == 200 else None


# ---------------------------------------------------------------- Ergebnisse

STEPS = []


def rec(sid, name, status, ev=""):
    STEPS.append({"id": sid, "name": name, "status": status, "evidence": san(ev, 260)})
    print(f"STEP {sid:6} {status:5} | {name} | {san(ev, 160)}", flush=True)


def check(sid, name, cond, ev=""):
    rec(sid, name, "PASS" if cond else "FAIL", ev)
    return bool(cond)


def skip(sid, name, why):
    rec(sid, name, "SKIP", why)


def info(sid, name, ev):
    rec(sid, name, "INFO", ev)


def section(fn):
    def wrap(*a, **k):
        try:
            return fn(*a, **k)
        except SystemExit:
            raise
        except Exception as e:  # Abnahme bricht nie komplett ab
            rec(
                fn.__name__, f"Abschnitt {fn.__name__} Ausnahme", "FAIL", f"{type(e).__name__}: {e}"
            )

    wrap.__name__ = fn.__name__
    return wrap


# ---------------------------------------------------------------- Zustand

ST = {"acct": {}, "cl": {}, "ids": {}}


def register(role, rand):
    email = f"{SYNTH_PREFIX}{rand}-{role}@{SYNTH_DOMAIN}"
    pw = secrets.token_hex(12) + "Aa1!"
    SECRETS.add(pw)
    c = Client(API, label=role)
    r = c.post("/v1/auth/register", {"email": email, "password": pw}, csrf=False)
    ST["acct"][role] = {
        "email": email,
        "password": pw,
        "id": r.json.get("id") if r.code == 201 else None,
    }
    ST["cl"][role] = c
    return r


def verify_email_db(role):
    em = ST["acct"][role]["email"]
    pattern = re.escape(SYNTH_PREFIX) + r"[0-9a-f]{6}-[a-z0-9]+@" + re.escape(SYNTH_DOMAIN)
    if not re.fullmatch(pattern, em):
        raise SystemExit("ABBRUCH: keine synthetische Adresse")
    psql(
        f"update users set email_verified_at=now() where email='{em}' and email like '{SYNTH_PREFIX}%'"
    )


def login(role, label=None):
    login_gate()
    c = Client(API, label=label or role)
    a = ST["acct"][role]
    r = c.post("/v1/auth/login", {"email": a["email"], "password": a["password"]}, csrf=False)
    return c, r


def mk_person(c, first, last, bd, pref):
    r = c.post(
        "/v1/people",
        {
            "birth_first_names": first,
            "birth_last_name": last,
            "birth_date": bd,
            "preferred_name": pref,
        },
    )
    if r.code != 201:
        return r, None, None, None
    pid = r.json["id"]
    r2 = c.post(f"/v1/people/{pid}/calculations", {"as_of_date": dt.date.today().isoformat()})
    return r, pid, (r2.json["id"] if r2.code == 201 else None), r2


# ---------------------------------------------------------------- Textpruefung

text_quality = content_checks.text_quality


def eval_text(sid, label, obj):
    q = text_quality(obj)
    check(
        f"{sid}a",
        f"{label}: keine ungeloesten Platzhalter",
        not q["hits"],
        f"hits={len(q['hits'])} {q['hits'][:3]}",
    )
    check(
        f"{sid}b",
        f"{label}: Text nicht leer/plausible Laenge",
        q["words"] >= 60 and q["chars"] >= 300 and q["chars"] <= 150000 and q["empty_strings"] == 0,
        f"chars={q['chars']} words={q['words']} empty={q['empty_strings']} segs={q['prose_segments']}",
    )
    check(
        f"{sid}c",
        f"{label}: Sprache deutsch",
        q["de"] >= 0.10 and q["de"] > 2 * q["en"],
        f"de={q['de']} en={q['en']}",
    )
    return q


# ---------------------------------------------------------------- Abschnitt 0: Setup


@section
def s0_setup(rand):
    for role in ("a", "b", "c", "u", "admin"):
        r = register(role, rand)
        ok = (
            r.code == 201
            and r.json.get("email_verified_at") is None
            and "numra_session" in ST["cl"][role].jar
        )
        if r.code == 429:
            check(
                "0.1" + role,
                f"Registrierung {role}",
                False,
                "429 Rate-Limit (auth:register 5/h pro IP) -> --reset-ratelimit oder 1h warten",
            )
            raise SystemExit("ABBRUCH: Registrierung nicht moeglich")
        check(
            "0.1" + role,
            f"Registrierung {role} (synthetisch, unverifiziert, Session-Cookie)",
            ok,
            r.short(),
        )
    for role in ("a", "b", "c", "admin"):
        verify_email_db(role)
    r = ST["cl"]["a"].get("/v1/auth/me")
    check(
        "0.2",
        "DB-Verifizierung A/B/C/Admin wirksam (me.email_verified_at gesetzt)",
        r.code == 200 and r.json.get("email_verified_at"),
        r.short(),
    )
    r = ST["cl"]["u"].get("/v1/auth/me")
    check(
        "0.3",
        "U bleibt unverifiziert",
        r.code == 200 and not r.json.get("email_verified_at"),
        r.short(),
    )


# ---------------------------------------------------------------- Abschnitt 1: Auth


def attrs(set_cookie):
    parts = [p.strip() for p in set_cookie.split(";")]
    name = parts[0].split("=")[0]
    low = [p.lower() for p in parts[1:]]
    return name, {
        "httponly": "httponly" in low,
        "secure": "secure" in low,
        "samesite": next((p.split("=")[1] for p in low if p.startswith("samesite=")), None),
        "path": next((p.split("=")[1] for p in low if p.startswith("path=")), None),
        "maxage": next((int(p.split("=")[1]) for p in low if p.startswith("max-age=")), None),
    }


def cookie_checks(sid, r, env, prefix=""):
    cks = dict(attrs(c) for c in r.set_cookies)
    s, c = cks.get("numra_session"), cks.get("numra_csrf")
    check(
        f"{sid}a",
        f"{prefix}Session-Cookie HttpOnly+SameSite=lax+Path=/",
        bool(s)
        and s["httponly"]
        and s["samesite"] == "lax"
        and s["path"] == "/"
        and (s["maxage"] or 0) > 0,
        str(s),
    )
    check(
        f"{sid}b",
        f"{prefix}CSRF-Cookie nicht HttpOnly, SameSite=lax",
        bool(c) and not c["httponly"] and c["samesite"] == "lax",
        str(c),
    )
    want_secure = env == "production"
    check(
        f"{sid}c",
        f"{prefix}Secure-Flag passend zur Config (ENVIRONMENT={env} -> Secure={want_secure})",
        bool(s) and bool(c) and s["secure"] == want_secure and c["secure"] == want_secure,
        f"session.secure={s and s['secure']} csrf.secure={c and c['secure']}",
    )


@section
def s1_auth(env):
    a = ST["acct"]["a"]
    c1 = ST["cl"]["a"]
    c2, r = login("a", "a-login")
    check(
        "1.1",
        "Login A -> 200 + Cookies",
        r.code == 200 and r.json.get("email") == a["email"],
        r.short(),
    )
    cookie_checks("1.2", r, env)
    r = c2.get("/v1/auth/me")
    check(
        "1.3",
        "me -> eigene Daten, role USER, aktiv",
        r.code == 200
        and r.json["email"] == a["email"]
        and str(r.json["role"]).endswith("USER")
        and r.json["is_active"],
        r.short(),
    )
    login_gate()
    r = Client(API).post(
        "/v1/auth/login",
        {"email": a["email"], "password": "falsch-" + secrets.token_hex(4)},
        csrf=False,
    )
    login_gate()
    r2 = Client(API).post(
        "/v1/auth/login",
        {
            "email": f"{SYNTH_PREFIX}{secrets.token_hex(3)}-nope@{SYNTH_DOMAIN}",
            "password": "x" * 14,
        },
        csrf=False,
    )
    check(
        "1.4",
        "falsches Passwort / unbekannte Mail -> identisch 401 INVALID_CREDENTIALS",
        r.code == 401 and r2.code == 401 and r.err == r2.err == "INVALID_CREDENTIALS",
        f"{r.short()} / {r2.short()}",
    )
    r = Client(API).get("/v1/auth/me")
    check("1.5", "me ohne Session -> 401", r.code == 401, r.short())
    s1, s2 = c1.get("/v1/auth/sessions"), c2.get("/v1/auth/sessions")
    cur1 = [x for x in (s1.json or []) if x["is_current"]]
    cur2 = [x for x in (s2.json or []) if x["is_current"]]
    check(
        "1.6",
        "Sessions: >=2 aktiv, je Client genau eine is_current",
        s1.code == 200
        and len(s1.json) >= 2
        and len(cur1) == 1
        and len(cur2) == 1
        and cur1[0]["id"] != cur2[0]["id"],
        f"n={len(s1.json or [])} cur={len(cur1)}/{len(cur2)}",
    )
    r = c2.post("/v1/auth/sessions/revoke-others", csrf=False)
    check(
        "1.7",
        "revoke-others ohne CSRF-Token -> 403 CSRF_VALIDATION_FAILED",
        r.code == 403 and r.err == "CSRF_VALIDATION_FAILED",
        r.short(),
    )
    r = c2.post("/v1/auth/sessions/revoke-others")
    old, cur = c1.get("/v1/auth/me"), c2.get("/v1/auth/me")
    n = c2.get("/v1/auth/sessions")
    check(
        "1.8",
        "revoke-others -> 204; alte Session 401, aktuelle 200, genau 1 Session",
        r.code == 204 and old.code == 401 and cur.code == 200 and len(n.json) == 1,
        f"{r.code} old={old.code} cur={cur.code} n={len(n.json or [])}",
    )
    old_jar = dict(c2.jar)
    r = c2.post("/v1/auth/logout")
    stale = Client(API)
    stale.jar = old_jar
    after = stale.get("/v1/auth/me")
    cleared = any(
        "max-age=0" in x.lower() or "expires=thu, 01 jan 1970" in x.lower() for x in r.set_cookies
    )
    check(
        "1.9",
        "logout -> 204, Cookies geloescht",
        r.code == 204 and cleared and "numra_session" not in c2.jar,
        f"{r.code} cleared={cleared}",
    )
    check(
        "1.10",
        "alte Session-Cookie nach Logout serverseitig ungueltig -> 401",
        after.code == 401,
        after.short(),
    )
    ST["cl"]["a"], r = login("a", "a-main")
    check("1.11", "erneuter Login A (Hauptsession)", r.code == 200, r.short())


# ---------------------------------------------------------------- Abschnitt 2: Zwei-Konten-Journey


@section
def s2_journey():
    A, B, _ = ST["cl"]["a"], ST["cl"]["b"], ST["cl"]["c"]
    ids = ST["ids"]
    ra = mk_person(A, "Anna", "Probe", "1990-03-14", "Anna")
    rb = mk_person(B, "Ben", "Muster", "1988-11-02", "Ben")
    ok = ra[1] and ra[2] and rb[1] and rb[2]
    check("2.1", "Person (SELF) + Berechnung fuer A und B", ok, f"A={ra[0].code} B={rb[0].code}")
    ids.update(pa=ra[1], ca=ra[2], pb=rb[1], cb=rb[2])
    # Einladung per LINK
    r = A.post("/v1/connections/invitations", {"method": "LINK"})
    tok = r.json.get("token") if r.code == 201 else None
    SECRETS.add(tok or "")
    check(
        "2.2",
        "A erstellt Einladung LINK -> 201, PENDING, Token+redeem_url",
        r.code == 201 and r.json["state"] == "PENDING" and tok and r.json.get("redeem_url"),
        r.short(),
    )
    inv_id = r.json["id"] if r.code == 201 else None
    r = B.get(f"/v1/connections/invitations/redeem/{tok}")
    check(
        "2.3",
        "B Vorschau (LINK) -> 200 method LINK, kein Inviter-PII",
        r.code == 200
        and r.json["method"] == "LINK"
        and set(r.json) <= {"id", "method", "expires_at"},
        r.short(),
    )
    r = A.post("/v1/connections/invitations/redeem", {"token": tok})
    inv_state = [i["state"] for i in A.get("/v1/connections/invitations").json if i["id"] == inv_id]
    check(
        "2.4",
        "Self-Accept eigener Einladung verboten (422 CANNOT_INVITE_SELF), Einladung bleibt PENDING",
        r.code == 422 and r.err == "CANNOT_INVITE_SELF" and inv_state == ["PENDING"],
        f"{r.short()} state={inv_state}",
    )
    r = B.post("/v1/connections/invitations/redeem", {"token": secrets.token_urlsafe(32)})
    check(
        "2.5",
        "ungueltiges Token -> 400 INVITATION_EXPIRED_OR_INVALID",
        r.code == 400 and r.err == "INVITATION_EXPIRED_OR_INVALID",
        r.short(),
    )
    anon = Client(API)
    anon.jar = {"numra_csrf": "anon-" + secrets.token_hex(8)}
    r = anon.post("/v1/connections/invitations/redeem", {"token": tok})
    check("2.6", "Redeem ohne Session (CSRF-Paar gueltig) -> 401", r.code == 401, r.short())
    r = B.post("/v1/connections/invitations/redeem", {"token": tok})
    ok = r.code == 201 and r.json["connection"]["status"] == "ACTIVE"
    check(
        "2.7",
        "B loest Token ein -> 201, Connection ACTIVE + workspace_id",
        ok and r.json.get("workspace_id"),
        r.short(),
    )
    if not ok:
        raise SystemExit("ABBRUCH: keine Connection A-B")
    ids["conn_ab"], ids["ws_ab"] = r.json["connection"]["id"], r.json["workspace_id"]
    r = B.post("/v1/connections/invitations/redeem", {"token": tok})
    check(
        "2.8",
        "benutztes Token (Replay) -> 400 INVITATION_EXPIRED_OR_INVALID",
        r.code == 400 and r.err == "INVITATION_EXPIRED_OR_INVALID",
        r.short(),
    )
    r = B.get(f"/v1/connections/invitations/redeem/{tok}")
    check("2.9", "Vorschau benutztes Token -> 400", r.code == 400, r.short())
    st = [i["state"] for i in A.get("/v1/connections/invitations").json if i["id"] == inv_id]
    check("2.10", "Einladung bei A jetzt ACCEPTED", st == ["ACCEPTED"], f"state={st}")
    ca, cb = A.get("/v1/connections").json, B.get("/v1/connections").json
    check(
        "2.11",
        "Connection-Liste beider Seiten: 1x ACTIVE, Gegenueber korrekt",
        len(ca) == 1
        and len(cb) == 1
        and ca[0]["status"] == "ACTIVE"
        and ca[0]["counterpart_user_id"] == ST["acct"]["b"]["id"]
        and cb[0]["counterpart_user_id"] == ST["acct"]["a"]["id"],
        f"A={len(ca)} B={len(cb)}",
    )
    r = A.get(f"/v1/workspaces/{ids['ws_ab']}")
    dp = (
        {m["user_id"]: m["core_numbers"] is not None for m in r.json["dual_profile"]}
        if r.code == 200
        else {}
    )
    check(
        "2.12",
        "Workspace ACTIVE, 2 Mitglieder, beide Kernzahlen sichtbar",
        r.code == 200
        and r.json["workspace"]["status"] == "ACTIVE"
        and len(dp) == 2
        and all(dp.values()),
        f"dp={list(dp.values())}",
    )
    r = A.patch(f"/v1/workspaces/{ids['ws_ab']}", {"relationship_type": "FRIENDSHIP"})
    check("2.13", "PATCH relationship_type FRIENDSHIP", r.code == 200, r.short())
    r = B.post("/v1/connections/invitations", {"method": "LINK"})
    r2 = (
        A.post("/v1/connections/invitations/redeem", {"token": r.json.get("token")})
        if r.code == 201
        else r
    )
    check(
        "2.14",
        "zweite Connection derselben Personen -> 409 CONNECTION_ALREADY_EXISTS",
        r2.code == 409 and r2.err == "CONNECTION_ALREADY_EXISTS",
        r2.short(),
    )
    # CODE-Methode: erstellen, Vorschau, widerrufen
    r = A.post("/v1/connections/invitations", {"method": "CODE"})
    ok = r.code == 201 and r.json["method"] == "CODE"
    cid, ctok = (r.json.get("id"), r.json.get("token")) if ok else (None, None)
    SECRETS.add(ctok or "")
    p = B.get(f"/v1/connections/invitations/redeem/{ctok}") if ok else None
    rv = A.post(f"/v1/connections/invitations/{cid}/revoke") if ok else None
    p2 = B.get(f"/v1/connections/invitations/redeem/{ctok}") if ok else None
    check(
        "2.15",
        "CODE-Einladung: erstellen 201, Vorschau 200, Revoke, danach Vorschau 400",
        ok and p.code == 200 and rv.code < 300 and p2.code == 400,
        f"{r.code}/{p and p.code}/{rv and rv.code}/{p2 and p2.code}",
    )


# ---------------------------------------------------------------- Abschnitt 3: G3 / E-Mail-Verifizierung


def mail_backend():
    """EMAIL_BACKEND des Containers; nicht erreichbar = Abbruch, nicht gesetzt = Default disabled."""
    rc, out = sh(
        [
            "docker",
            "exec",
            CONTAINERS["api"],
            *["sh", "-c", 'printf "%s" "${EMAIL_BACKEND-__unset__}"'],
        ]
    )
    if rc != 0:
        raise SystemExit(
            "VERWEIGERT: EMAIL_BACKEND im API-Container nicht lesbar (Container erreichbar?)"
        )
    value = out.strip()
    return "disabled" if value == "__unset__" else value


def mail_risk():
    """True, wenn das Ziel echte Mails versenden koennte (EMAIL_BACKEND=smtp)."""
    backend = ST.get("mail_backend") or mail_backend() or "disabled"
    return backend == "smtp", backend


@section
def s3_g3():
    A, C, U = ST["cl"]["a"], ST["cl"]["c"], ST["cl"]["u"]
    ids = ST["ids"]
    risky, detail = mail_risk()
    check(
        "3.0",
        "Mail-Sicherheit: EMAIL_BACKEND des api-Containers versendet keine echten Mails",
        not risky,
        f"EMAIL_BACKEND={detail}",
    )
    r = U.post("/v1/connections/invitations", {"method": "LINK"})
    check(
        "3.1",
        "G3: unverifiziertes Konto erstellt Einladung -> 403 EMAIL_VERIFICATION_REQUIRED",
        r.code == 403 and r.err == "EMAIL_VERIFICATION_REQUIRED",
        r.short(),
    )
    rc = C.post("/v1/connections/invitations", {"method": "LINK"})
    r = (
        U.post("/v1/connections/invitations/redeem", {"token": rc.json.get("token")})
        if rc.code == 201
        else rc
    )
    check(
        "3.2",
        "G3: unverifiziertes Konto loest LINK-Einladung ein -> 403 EMAIL_VERIFICATION_REQUIRED",
        r.code == 403 and r.err == "EMAIL_VERIFICATION_REQUIRED",
        r.short(),
    )
    if r.code == 201:
        info(
            "3.2i",
            "Beobachtung S1: unverifiziertes U hat LINK-Einladung von C eingeloest (Connection C-U angelegt)",
            "erwartet auf S1",
        )
    if risky:
        for sid, n in (
            ("3.3", "EMAIL-Einladung, unverifizierter Empfaenger"),
            ("3.4", "Einladung bleibt PENDING"),
            ("3.5", "falsche Empfaengeradresse"),
            ("3.6", "Selbsteinladung per EMAIL"),
        ):
            skip(sid, n, "SKIP: EMAIL_BACKEND=smtp, kein Mailversand aus der Abnahme (3.0)")
    else:
        r = A.post(
            "/v1/connections/invitations",
            {"method": "EMAIL", "invitee_email": ST["acct"]["u"]["email"]},
        )
        etok, eid = (r.json.get("token"), r.json.get("id")) if r.code == 201 else (None, None)
        SECRETS.add(etok or "")
        ids["email_inv"] = (eid, etok)
        check(
            "3.3a",
            "A erstellt EMAIL-Einladung an U (ohne Mailversand) -> 201",
            r.code == 201 and r.json["method"] == "EMAIL",
            r.short(),
        )
        r = U.post("/v1/connections/invitations/redeem", {"token": etok})
        check(
            "3.3",
            "EMAIL-Einladung, Empfaenger unverifiziert -> 403 EMAIL_VERIFICATION_REQUIRED",
            r.code == 403 and r.err == "EMAIL_VERIFICATION_REQUIRED",
            r.short(),
        )
        stt = [i["state"] for i in A.get("/v1/connections/invitations").json if i["id"] == eid]
        check(
            "3.4",
            "abgelehnte Einloesung verbrennt Einladung nicht (PENDING)",
            stt == ["PENDING"],
            f"state={stt}",
        )
        other = f"{SYNTH_PREFIX}{secrets.token_hex(3)}-other@{SYNTH_DOMAIN}"
        r = A.post("/v1/connections/invitations", {"method": "EMAIL", "invitee_email": other})
        r2 = (
            C.post("/v1/connections/invitations/redeem", {"token": r.json.get("token")})
            if r.code == 201
            else r
        )
        check(
            "3.5",
            "EMAIL-Einladung, falscher (verifizierter) Einloeser -> 400 INVITATION_EXPIRED_OR_INVALID",
            r2.code == 400 and r2.err == "INVITATION_EXPIRED_OR_INVALID",
            r2.short(),
        )
        r = A.post(
            "/v1/connections/invitations",
            {"method": "EMAIL", "invitee_email": ST["acct"]["a"]["email"]},
        )
        check(
            "3.6",
            "Selbsteinladung per EMAIL -> 422 CANNOT_INVITE_SELF",
            r.code == 422 and r.err == "CANNOT_INVITE_SELF",
            r.short(),
        )
    verify_email_db("u")
    r = U.get("/v1/auth/me")
    check(
        "3.7",
        "U per DB-UPDATE verifiziert (me.email_verified_at gesetzt)",
        r.code == 200 and bool(r.json.get("email_verified_at")),
        r.short(),
    )
    r = U.post("/v1/connections/invitations", {"method": "LINK"})
    check("3.8", "verifiziertes U erstellt Einladung -> 201", r.code == 201, r.short())
    pu = mk_person(U, "Uwe", "Verifiziert", "1975-07-23", "Uwe")
    check("3.9", "Person+Berechnung fuer U", bool(pu[1] and pu[2]), pu[0].code)
    ids.update(pu_=pu[1], cu=pu[2])
    if not risky and ids.get("email_inv") and ids["email_inv"][1]:
        r = U.post("/v1/connections/invitations/redeem", {"token": ids["email_inv"][1]})
        ok = r.code == 201 and r.json["connection"]["status"] == "ACTIVE"
        check(
            "3.10",
            "verifizierter Empfaenger loest EMAIL-Einladung ein -> 201 (Connection A-U)",
            ok,
            r.short(),
        )
        if ok:
            ids["ws_au"] = r.json["workspace_id"]
    if not ids.get("ws_au"):
        r = A.post("/v1/connections/invitations", {"method": "LINK"})
        r = (
            U.post("/v1/connections/invitations/redeem", {"token": r.json.get("token")})
            if r.code == 201
            else r
        )
        if r.code == 201:
            ids["ws_au"] = r.json["workspace_id"]
        check("3.10f", "Fallback: Connection A-U per LINK", r.code == 201, r.short())
    if ids.get("ws_au"):
        r = A.patch(f"/v1/workspaces/{ids['ws_au']}", {"relationship_type": "PARTNER"})
        check("3.11", "Workspace A-U relationship_type PARTNER", r.code == 200, r.short())


# ---------------------------------------------------------------- Abschnitt 6/7/10: LLM-Jobs


JOBS = {}


@section
def llm_start():
    A = ST["cl"]["a"]
    ids = ST["ids"]
    for key, ws in (("an1", ids.get("ws_ab")), ("an2", ids.get("ws_au"))):
        if not ws:
            skip({"an1": "6.0", "an2": "10.0"}[key], f"Analyse {key} starten", "kein Workspace")
            continue
        r = A.post(
            f"/v1/workspaces/{ws}/relationship-analysis",
            {},
            headers={"Idempotency-Key": SYNTH_PREFIX + secrets.token_hex(6)},
        )
        sid = {"an1": "6.1", "an2": "10.1"}[key]
        ok = r.code == 201
        check(
            sid,
            f"Relationship-Analyse starten ({key}, "
            + ("FRIENDSHIP A-B" if key == "an1" else "PARTNER A-U")
            + ")",
            ok,
            f"{r.short()} status={r.json.get('status') if ok else ''}",
        )
        if ok:
            JOBS[key] = {
                "kind": "analysis",
                "ws": ws,
                "analysis_id": r.json["id"],
                "job_id": r.json["job_id"],
                "t0": time.time(),
                "status": None,
            }
    r = A.post("/v1/reports", {"calculation_id": ids["ca"], "report_type": "QUICK"})
    ok = r.code == 201
    check("7.1", "Report (QUICK) fuer A starten", ok, r.short())
    if ok:
        JOBS["report"] = {
            "kind": "report",
            "report_id": r.json["id"],
            "job_id": r.json["job_id"],
            "t0": time.time(),
            "status": None,
        }


@section
def llm_poll(timeout):
    A = ST["cl"]["a"]
    end = time.time() + timeout
    while time.time() < end and any(
        j["status"] not in ("COMPLETE", "FAILED", "CANCELLED") for j in JOBS.values()
    ):
        for j in JOBS.values():
            if j["status"] in ("COMPLETE", "FAILED", "CANCELLED"):
                continue
            path = (
                f"/v1/analysis-jobs/{j['job_id']}"
                if j["kind"] == "analysis"
                else f"/v1/report-jobs/{j['job_id']}"
            )
            r = A.get(path)
            if r.code == 200:
                j["status"], j["error_code"], j["progress"] = (
                    r.json["status"],
                    r.json.get("error_code"),
                    r.json.get("progress"),
                )
                if j["status"] in ("COMPLETE", "FAILED", "CANCELLED"):
                    j["dur"] = int(time.time() - j["t0"])
        time.sleep(8)
    for j in JOBS.values():
        if j["status"] not in ("COMPLETE", "FAILED", "CANCELLED"):
            j["timeout"] = True


def llm_row(job_col, job_id, source):
    out = psql(
        f"select count(*) filter (where status='ok'), coalesce(sum(total_tokens),0), count(*), coalesce(max(model),'') from llm_generations where source='{source}' and {job_col}='{need_uuid(job_id)}'"
    )
    ok_n, tok, n, model = (out.split("|") + ["", "", "", ""])[:4]
    return int(ok_n or 0), int(tok or 0), int(n or 0), model


@section
def llm_eval():
    A, B, U = ST["cl"]["a"], ST["cl"]["b"], ST["cl"]["u"]
    texts = {}
    for key, base, name in (
        ("an1", "6", "Analyse 1 (A-B, FRIENDSHIP)"),
        ("an2", "10", "Analyse 2 (A-U, PARTNER)"),
    ):
        j = JOBS.get(key)
        if not j:
            skip(f"{base}.2", name, "nicht gestartet")
            continue
        ev = f"status={j['status']} err={j.get('error_code')} dauer={j.get('dur')}s" + (
            " TIMEOUT" if j.get("timeout") else ""
        )
        if not check(
            f"{base}.2", f"{name}: Job COMPLETE (Timeout 10 min)", j["status"] == "COMPLETE", ev
        ):
            info(f"{base}.2f", f"{name}: Fehlerfall dokumentiert", ev)
            continue
        r = A.get(f"/v1/workspaces/{j['ws']}/relationship-analysis/{j['analysis_id']}")
        check(
            f"{base}.3",
            f"{name}: Ergebnis lesbar, result vorhanden",
            r.code == 200 and bool(r.json.get("result")),
            f"{r.short()} status={r.json and r.json.get('status')} model={r.json and r.json.get('model_name')}",
        )
        if r.code != 200:
            continue
        texts[key] = json.dumps(r.json["result"], sort_keys=True)
        eval_text(f"{base}.4", name, r.json["result"])
        ok_n, tok, n, model = llm_row("analysis_job_id", j["job_id"], "analysis")
        check(
            f"{base}.5",
            f"{name}: llm_generations source=analysis, status ok",
            ok_n >= 1,
            f"rows={n} ok={ok_n} model={model}",
        )
        check(
            f"{base}.5t",
            f"{name}: llm_generations Tokens>0 (Summe total_tokens)",
            tok > 0,
            f"tokens={tok} (NULL/0 = Provider meldet keine Usage oder Erfassung fehlt)",
        )
        if j.get("error_code"):
            info(
                f"{base}.2e",
                f"{name}: Job COMPLETE, aber error_code gesetzt (Rest eines Retry-Versuchs)",
                f"error_code={j['error_code']}",
            )
        rb = (B if key == "an1" else U).get(f"/v1/workspaces/{j['ws']}/relationship-analysis")
        check(
            f"{base}.6",
            f"{name}: Gegenueber (Mitglied) kann Analyse lesen",
            rb.code == 200,
            rb.short(),
        )
    if "an1" in texts and "an2" in texts:
        check(
            "10.9",
            "Die zwei Analysen sind inhaltlich verschieden (andere Profile/Beziehungsart)",
            texts["an1"] != texts["an2"],
            f"len={len(texts['an1'])}/{len(texts['an2'])}",
        )
    # Report + PDF
    j = JOBS.get("report")
    if not j:
        skip("7.2", "Report-Job", "nicht gestartet")
        return
    ev = f"status={j['status']} err={j.get('error_code')} dauer={j.get('dur')}s" + (
        " TIMEOUT" if j.get("timeout") else ""
    )
    if not check("7.2", "Report-Job COMPLETE (Timeout 10 min)", j["status"] == "COMPLETE", ev):
        info("7.2f", "Report: Fehlerfall dokumentiert", ev)
        return
    r = A.get(f"/v1/reports/{j['report_id']}")
    check(
        "7.3",
        "Report lesbar, content vorhanden",
        r.code == 200 and bool(r.json.get("content")),
        r.short(),
    )
    if r.code == 200 and r.json.get("content"):
        eval_text("7.4", "Report", r.json["content"])
    ok_n, tok, n, model = llm_row("report_job_id", j["job_id"], "report")
    check(
        "7.5",
        "llm_generations source=report, status ok",
        ok_n >= 1,
        f"rows={n} ok={ok_n} model={model}",
    )
    check(
        "7.5t",
        "llm_generations (report) Tokens>0 (Summe total_tokens)",
        tok > 0,
        f"tokens={tok} (NULL/0 = Provider meldet keine Usage oder Erfassung fehlt)",
    )
    r = A.post("/v1/exports", {"report_id": j["report_id"], "export_type": "pdf"}, timeout=180)
    ok = r.code == 201
    check(
        "7.6",
        "PDF-Export erzeugen -> 201",
        ok,
        f"{r.short()} status={r.json.get('status') if ok else ''}",
    )
    if not ok:
        return
    eid = r.json["id"]
    for _ in range(30):
        lst = A.get("/v1/exports").json or []
        cur = [e for e in lst if e["id"] == eid]
        if cur and cur[0]["status"] in ("complete", "failed"):
            break
        time.sleep(4)
    check(
        "7.7",
        "Export-Status complete",
        bool(cur) and cur[0]["status"] == "complete",
        f"status={cur and cur[0]['status']} err={cur and cur[0].get('error_code')}",
    )
    d = A.get(f"/v1/exports/{eid}/download", timeout=120)
    pdf = d.raw or b""
    check(
        "7.8",
        "PDF-Download: 200, application/pdf, Magic %PDF, %%EOF, Groesse>20KB",
        d.code == 200
        and "pdf" in (d.headers.get("Content-Type") or "")
        and pdf[:4] == b"%PDF"
        and b"%%EOF" in pdf[-2048:]
        and len(pdf) > content_checks.MIN_PDF_BYTES,
        f"{d.code} bytes={len(pdf)} ct={d.headers.get('Content-Type')}",
    )
    analysis = content_checks.analyze_pdf(pdf)
    for suffix, name, passed, evidence in content_checks.evaluate_pdf(analysis):
        check(f"7.{suffix}", name, passed, evidence)
    x = B.get(f"/v1/exports/{eid}/download")
    check("7.11", "fremdes Konto (B) kann Export nicht laden -> 404", x.code == 404, x.short())


# ---------------------------------------------------------------- Abschnitt 4: Consent


def overview_core(c, ws):
    r = c.get(f"/v1/workspaces/{ws}")
    if r.code != 200:
        return r, None
    return r, {m["user_id"]: m["core_numbers"] is not None for m in r.json["dual_profile"]}


@section
def s4_consent():
    A, B, C = ST["cl"]["a"], ST["cl"]["b"], ST["cl"]["c"]
    ids, ua, ub = ST["ids"], ST["acct"]["a"]["id"], ST["acct"]["b"]["id"]
    ws = ids["ws_ab"]
    r = A.get(f"/v1/workspaces/{ws}/consent")
    by, to = (r.json["granted_by_me"], r.json["granted_to_me"]) if r.code == 200 else ([], [])
    check(
        "4.1",
        "Default-Consent: 3 Scopes je Richtung aktiv",
        r.code == 200
        and len(by) == 3
        and len(to) == 3
        and all(g["revoked_at"] is None for g in by + to),
        f"by={len(by)} to={len(to)}",
    )
    ra, da = overview_core(A, ws)
    rb, db_ = overview_core(B, ws)
    check(
        "4.2",
        "Baseline: A sieht Kernzahlen von B, B die von A",
        da and da.get(ub) and db_ and db_.get(ua),
        f"A->B={da and da.get(ub)} B->A={db_ and db_.get(ua)}",
    )
    th = A.post(f"/v1/workspaces/{ws}/copilot/threads", {"scope": "RELATIONSHIP_SHARED"})
    thid = th.json.get("id") if th.code == 201 else None
    r = B.post(f"/v1/workspaces/{ws}/consent/revoke", {"scope": "CORE_NUMEROLOGY"})
    check(
        "4.3",
        "B widerruft CORE_NUMEROLOGY -> 2xx, revoked_at gesetzt",
        r.code < 300 and r.json.get("revoked_at"),
        r.short(),
    )
    ra, da = overview_core(A, ws)
    rb, db_ = overview_core(B, ws)
    check(
        "4.4",
        "Zugriffsverlust: A sieht B-Kernzahlen NICHT mehr (core_numbers=null)",
        ra.code == 200 and da.get(ub) is False,
        f"A->B={da and da.get(ub)}",
    )
    check(
        "4.5",
        "B sieht A-Kernzahlen weiterhin (Richtung unberuehrt)",
        db_ and db_.get(ua) is True,
        f"B->A={db_ and db_.get(ua)}",
    )
    r = B.post(f"/v1/workspaces/{ws}/consent/revoke", {"scope": "CORE_NUMEROLOGY"})
    check(
        "4.6",
        "doppelter Revoke -> 403 CONSENT_NOT_GRANTED",
        r.code == 403 and r.err == "CONSENT_NOT_GRANTED",
        r.short(),
    )
    r = A.post(f"/v1/workspaces/{ws}/consent/revoke", {"scope": "RELATIONSHIP_INSIGHTS"})
    r2 = A.post(f"/v1/workspaces/{ws}/relationship-analysis", {})
    r3 = B.post(f"/v1/workspaces/{ws}/relationship-analysis", {})
    check(
        "4.7",
        "A widerruft RELATIONSHIP_INSIGHTS -> neue Analyse fuer A und B: 403 CONSENT_NOT_GRANTED",
        r.code < 300 and r2.code == 403 and r2.err == "CONSENT_NOT_GRANTED" and r3.code == 403,
        f"revoke={r.code} A={r2.short()} B={r3.short()}",
    )
    if not thid:
        skip(
            "4.8",
            "Shared-Copilot-Nachricht unter widerrufenem Consent",
            f"Thread nicht anlegbar: {th.short()}",
        )
    else:
        t = A.post(
            f"/v1/workspaces/{ws}/copilot/threads/{thid}/messages",
            {"content": "Was ist eine gute Gewohnheit fuer uns beide?"},
            timeout=300,
        )
        check(
            "4.8",
            "Shared-Copilot-Nachricht bei widerrufenem Consent -> 403 CONSENT_NOT_GRANTED (kein LLM-Aufruf)",
            t.code == 403 and t.err == "CONSENT_NOT_GRANTED",
            t.short(),
        )
    probes = {
        "checkins/current": "GET",
        "checkins": "GET",
        "tasks": "GET",
        "shared-reflections": "GET",
        "relationship-analysis": "GET",
        "shadow-dynamics": "GET",
    }
    obs = {}
    for p in probes:
        obs[p] = A.get(f"/v1/workspaces/{ws}/{p}").code
    info(
        "4.9",
        "Beobachtung Folgerouten fuer A nach Revoke (kein Consent-Gate im Code; Check-ins liefern nur eigene Werte, Analyse = bereits erzeugte Historie)",
        str(obs),
    )
    # Cross-user IDOR auf B-Ressourcen
    o = {
        "people": A.get(f"/v1/people/{ids['pb']}").code,
        "people/calcs": A.get(f"/v1/people/{ids['pb']}/calculations").code,
        "calc": A.get(f"/v1/calculations/{ids['cb']}").code,
        "notes": A.get(f"/v1/people/{ids['pb']}/private-notes").code,
    }
    check(
        "4.10",
        "A kann Person/Berechnung/Notizen von B direkt nie lesen (404)",
        all(v == 404 for v in o.values()),
        str(o),
    )
    # Re-Grant
    r1 = B.post(f"/v1/workspaces/{ws}/consent/grant", {"scope": "CORE_NUMEROLOGY"})
    r2 = A.post(f"/v1/workspaces/{ws}/consent/grant", {"scope": "RELATIONSHIP_INSIGHTS"})
    ra, da = overview_core(A, ws)
    check(
        "4.11",
        "Re-Grant CORE_NUMEROLOGY/RELATIONSHIP_INSIGHTS -> 2xx, A sieht B-Kernzahlen wieder",
        r1.code < 300 and r2.code < 300 and da.get(ub) is True,
        f"{r1.code}/{r2.code} A->B={da and da.get(ub)}",
    )
    r = B.post(f"/v1/workspaces/{ws}/consent/grant", {"scope": "CORE_NUMEROLOGY"})
    check("4.12", "Grant idempotent (bereits aktiv) -> 2xx", r.code < 300, r.short())
    # IDOR: dritte Person C
    an = JOBS.get("an1", {}).get("analysis_id")
    jb = JOBS.get("an1", {}).get("job_id")
    idor = {
        "ws": C.get(f"/v1/workspaces/{ws}").code,
        "consent": C.get(f"/v1/workspaces/{ws}/consent").code,
        "grant": C.post(f"/v1/workspaces/{ws}/consent/grant", {"scope": "CORE_NUMEROLOGY"}).code,
        "revoke": C.post(f"/v1/workspaces/{ws}/consent/revoke", {"scope": "CORE_NUMEROLOGY"}).code,
        "analysis_latest": C.get(f"/v1/workspaces/{ws}/relationship-analysis").code,
        "analysis_post": C.post(f"/v1/workspaces/{ws}/relationship-analysis", {}).code,
        "shadow": C.get(f"/v1/workspaces/{ws}/shadow-dynamics").code,
        "checkins": C.get(f"/v1/workspaces/{ws}/checkins/current").code,
        "tasks": C.get(f"/v1/workspaces/{ws}/tasks").code,
        "conn_dissolve": C.post(f"/v1/connections/{ids['conn_ab']}/dissolve").code,
    }
    if an:
        idor["analysis_by_id"] = C.get(f"/v1/workspaces/{ws}/relationship-analysis/{an}").code
        idor["job"] = C.get(f"/v1/analysis-jobs/{jb}").code
    check(
        "4.14",
        "IDOR: dritte Person ohne Zugriff erhaelt ueberall 404 (503 nur wenn Feature-Flag aus)",
        all(v in (404, 503) for v in idor.values())
        and sum(v == 404 for v in idor.values()) >= len(idor) - 2,
        str(idor),
    )
    # Dissolution
    r = A.post(f"/v1/connections/{ids['conn_ab']}/dissolve")
    check(
        "4.15",
        "A loest Connection auf -> 200 DISSOLVED",
        r.code == 200 and r.json.get("status") == "DISSOLVED",
        r.short(),
    )
    r = A.post(f"/v1/connections/{ids['conn_ab']}/dissolve")
    check(
        "4.16",
        "Dissolve idempotent",
        r.code == 200 and r.json.get("status") == "DISSOLVED",
        r.short(),
    )
    r = A.get(f"/v1/workspaces/{ws}/consent")
    act = (
        sum(
            1
            for g in (r.json["granted_by_me"] + r.json["granted_to_me"])
            if g["revoked_at"] is None
        )
        if r.code == 200
        else -1
    )
    check(
        "4.18",
        "nach Dissolution: alle Consent-Grants widerrufen (0 aktiv)",
        act == 0,
        f"aktiv={act}",
    )
    ra, da = overview_core(A, ws)
    rb, db_ = overview_core(B, ws)
    check(
        "4.19",
        "nach Dissolution: kein Partner-Kernzahlzugriff mehr, Workspace DISSOLVED",
        da.get(ub) is False
        and db_.get(ua) is False
        and ra.json["workspace"]["status"] == "DISSOLVED",
        f"A->B={da.get(ub)} B->A={db_.get(ua)}",
    )
    r = B.post(f"/v1/workspaces/{ws}/consent/grant", {"scope": "CORE_NUMEROLOGY"})
    check(
        "4.17",
        "Grant nach Dissolution -> 409 WORKSPACE_DISSOLVED",
        r.code == 409 and r.err == "WORKSPACE_DISSOLVED",
        r.short(),
    )
    r = A.get(f"/v1/workspaces/{ws}/consent")
    act2 = (
        sum(
            1
            for g in (r.json["granted_by_me"] + r.json["granted_to_me"])
            if g["revoked_at"] is None
        )
        if r.code == 200
        else -1
    )
    check(
        "4.17b",
        "Grant nach Dissolution hinterlaesst keinen aktiven Consent (0 aktiv)",
        act2 == 0,
        f"aktiv={act2}",
    )
    r = A.post(f"/v1/workspaces/{ws}/relationship-analysis", {})
    check(
        "4.20",
        "neue Analyse nach Dissolution -> 409 WORKSPACE_DISSOLVED",
        r.code == 409 and r.err == "WORKSPACE_DISSOLVED",
        r.short(),
    )
    info(
        "4.21",
        "Beobachtung nach Dissolution: Analyse-Historie lesbar (Design: read-only erhalten)",
        f"A={A.get(f'/v1/workspaces/{ws}/relationship-analysis').code} B={B.get(f'/v1/workspaces/{ws}/relationship-analysis').code}",
    )
    check(
        "4.22",
        "A-U Workspace bleibt von Dissolution A-B unberuehrt (ACTIVE)",
        A.get(f"/v1/workspaces/{ids['ws_au']}").json["workspace"]["status"] == "ACTIVE"
        if ids.get("ws_au")
        else True,
        "",
    )
    cc = C.get(f"/v1/workspaces/{ws}")
    check(
        "4.23",
        "IDOR C nach Dissolution weiter 404 (kein 409-Leak)",
        cc.code == 404
        and C.post(f"/v1/workspaces/{ws}/consent/grant", {"scope": "CORE_NUMEROLOGY"}).code == 404,
        cc.short(),
    )


# ---------------------------------------------------------------- Abschnitt 5: Admin


@section
def s5_admin():
    AD, A = ST["cl"]["admin"], ST["cl"]["a"]
    email = ST["acct"]["admin"]["email"]
    rc, out = sh(
        [
            "docker",
            "exec",
            CONTAINERS["api"],
            "python",
            "-m",
            "numra_api.cli",
            "admin",
            "promote-admin",
            "--email",
            email,
        ]
    )
    check(
        "5.1",
        "promote-admin per CLI im Audit-API-Container",
        rc == 0 and "promoted" in out,
        san(out, 80),
    )
    r = AD.get("/v1/auth/me")
    if not str(r.json.get("role", "")).endswith("ADMIN"):
        AD, _ = login("admin")
        ST["cl"]["admin"] = AD
        r = AD.get("/v1/auth/me")
    check(
        "5.2",
        "Admin-Rolle in /me",
        r.code == 200 and str(r.json["role"]).endswith("ADMIN"),
        r.short(),
    )
    admin_id = r.json["id"]
    r = AD.get("/v1/admin/flags")
    flags = {f["name"]: f["enabled"] for f in r.json["flags"]} if r.code == 200 else {}
    check(
        "5.3",
        "GET /v1/admin/flags -> Flag 'checkins' vorhanden",
        r.code == 200 and "checkins" in flags,
        f"n={len(flags)} checkins={flags.get('checkins')}",
    )
    if "checkins" not in flags:
        return
    orig = flags["checkins"]
    anon = Client(API)
    probe = lambda: anon.get(f"/v1/workspaces/{ZERO}/checkins").code
    p0 = probe()
    check(
        "5.4",
        "Probe vorher entspricht Ausgangswert (an=401 / aus=503)",
        p0 == (401 if orig else 503),
        f"flag={orig} probe={p0}",
    )
    flip = not orig
    try:
        r = AD.patch("/v1/admin/flags/checkins", {"enabled": flip})
        time.sleep(1.5)
        p1 = probe()
        check(
            "5.5",
            "Flag checkins umgeschaltet -> Probe wechselt (an=401 / aus=503)",
            r.code in (200, 204) and p1 == (401 if flip else 503),
            f"patch={r.code} probe={p1}",
        )
    finally:
        r = AD.patch("/v1/admin/flags/checkins", {"enabled": orig})
        time.sleep(1.5)
        p2 = probe()
        fl = {f["name"]: f["enabled"] for f in AD.get("/v1/admin/flags").json["flags"]}
        check(
            "5.6",
            "Ausgangswert wiederhergestellt (Flag+Probe)",
            r.code in (200, 204) and fl["checkins"] == orig and p2 == p0,
            f"patch={r.code} flag={fl['checkins']} probe={p2}",
        )
    r = AD.get("/v1/admin/audit?page_size=100")
    if r.code != 200:
        r = AD.get("/v1/admin/audit?page_size=50")
    ev = [
        i
        for i in (r.json or {}).get("items", [])
        if i["action"] == "FEATURE_FLAG_CHANGED" and i["actor_user_id"] == admin_id
    ]
    check(
        "5.7",
        "Auditlog enthaelt >=2 FEATURE_FLAG_CHANGED mit actor = Admin",
        r.code == 200 and len(ev) >= 2,
        f"{r.code} treffer={len(ev)} meta_keys={sorted(ev[0]['safe_metadata']) if ev else ''}",
    )
    pe = [
        i
        for i in (r.json or {}).get("items", [])
        if i["action"] == "ADMIN_PROMOTED" and i["target_user_id"] == admin_id
    ]
    check(
        "5.8", "Auditlog enthaelt ADMIN_PROMOTED fuer den Admin", len(pe) >= 1, f"treffer={len(pe)}"
    )
    codes = [
        A.get("/v1/admin/flags").code,
        A.get("/v1/admin/audit").code,
        A.get("/v1/admin/stats").code,
        A.get("/v1/admin/users").code,
        A.patch("/v1/admin/flags/checkins", {"enabled": orig}).code,
    ]
    check("5.9", "Nicht-Admin: Admin-Routen -> 403", all(c == 403 for c in codes), str(codes))
    anon_codes = [anon.get("/v1/admin/flags").code, anon.get("/v1/admin/audit").code]
    check(
        "5.10",
        "ohne Session: Admin-Routen -> 401",
        all(c == 401 for c in anon_codes),
        str(anon_codes),
    )


# ---------------------------------------------------------------- Abschnitt 8: Web-Proxy


@section
def s8_proxy():
    a = ST["acct"]["c"]
    P = Client(WEB, prefix="/api", label="c-proxy")
    login_gate()
    r = P.post(
        "/v1/auth/login",
        {"email": a["email"], "password": a["password"]},
        csrf=False,
        headers={"Origin": WEB},
    )
    env = ST["env"]
    check(
        "8.1",
        "Login ueber Web-Proxy /api/v1/auth/login -> 200",
        r.code == 200 and r.json and r.json.get("email") == a["email"],
        r.short(),
    )
    cks = dict(attrs(c) for c in r.set_cookies)
    check(
        "8.2",
        "Set-Cookie wird weitergereicht (numra_session HttpOnly+SameSite=lax, numra_csrf lesbar)",
        "numra_session" in cks
        and cks["numra_session"]["httponly"]
        and cks["numra_session"]["samesite"] == "lax"
        and "numra_csrf" in cks
        and not cks["numra_csrf"]["httponly"],
        f"cookies={sorted(cks)}",
    )
    check(
        "8.3",
        "Secure-Flag ueber Proxy passend zur Config",
        all(v["secure"] == (env == "production") for v in cks.values()) and bool(cks),
        f"env={env} secure={[v['secure'] for v in cks.values()]}",
    )
    m = P.get("/v1/auth/me")
    check("8.4", "me ueber Proxy mit weitergereichtem Cookie -> 200", m.code == 200, m.short())
    ep = "/v1/auth/sessions/revoke-others"
    r = P.post(ep, csrf=False, headers={"Origin": WEB})
    check(
        "8.5",
        "mutierender Request ohne x-csrf-token -> 403 CSRF_VALIDATION_FAILED",
        r.code == 403 and r.err == "CSRF_VALIDATION_FAILED",
        r.short(),
    )
    r = P.post(ep, csrf="ungueltig-" + secrets.token_hex(8), headers={"Origin": WEB})
    check(
        "8.6",
        "ungueltiger x-csrf-token -> 403 CSRF_VALIDATION_FAILED",
        r.code == 403 and r.err == "CSRF_VALIDATION_FAILED",
        r.short(),
    )
    r = P.post(ep, headers={"Origin": "https://evil.example"})
    check(
        "8.7",
        "fremde Origin (gueltiger Token) -> 403 ORIGIN_NOT_ALLOWED",
        r.code == 403 and r.err == "ORIGIN_NOT_ALLOWED",
        r.short(),
    )
    r = P.post(ep, headers={"Origin": WEB})
    check("8.8", "mit gueltigem Token + erlaubter Origin -> 204", r.code == 204, r.short())
    r = P.post("/v1/auth/logout", headers={"Origin": WEB})
    after = P.get("/v1/auth/me", use_cookies=False)
    check(
        "8.9",
        "Logout ueber Proxy -> 204; danach 401",
        r.code == 204 and after.code == 401,
        f"{r.code}/{after.code}",
    )


# ---------------------------------------------------------------- Abschnitt 9: Worker / Queue / Logs


@section
def s9_workers(t_start):
    time.sleep(3)
    q = {}
    for t in ("analysis_jobs", "report_jobs"):
        q[t] = int(
            psql(
                f"select count(*) from {t} where status='QUEUED' and created_at < now() - interval '2 minutes'"
            )
            or 0
        )
    check(
        "9.1",
        "keine QUEUED-Jobs aelter 2 min (analysis_jobs/report_jobs)",
        sum(q.values()) == 0,
        str(q),
    )
    stuck = int(
        psql(
            "select count(*) from analysis_jobs where status in ('GENERATING','VALIDATING') and updated_at < now() - interval '15 minutes'"
        )
        or 0
    )
    check(
        "9.2",
        "keine haengenden Analyse-Jobs (GENERATING/VALIDATING >15 min)",
        stuck == 0,
        f"stuck={stuck}",
    )
    since = t_start.strftime("%Y-%m-%dT%H:%M:%SZ")
    for key in ("worker", "aworker", "api"):
        cn = CONTAINERS[key]
        rc, out = sh(["docker", "logs", "--since", since, cn], timeout=60)
        lines = out.splitlines()
        tb = sum(1 for ln in lines if "Traceback" in ln)
        er = [
            ln
            for ln in lines
            if re.search(
                r'\bERROR\b|\bCRITICAL\b|"level": ?"(error|critical)"|level=(error|critical)', ln
            )
        ]
        s5 = sum(1 for ln in lines if re.search(r'"status_code": ?5\d\d|status_code=5\d\d', ln))
        heads = []
        for ln in er[:3]:
            ln = re.sub(r"^\S*\d{4}-\d\d-\d\dT\S+\s*", "", ln)
            heads.append(san(ln, 90))
        if key == "aworker":
            cls = {
                k: sum(1 for ln in lines if k in ln)
                for k in (
                    "MalformedPlaceholder",
                    "PromptScaffoldingRejected",
                    "ANALYSIS_VALIDATION_FAILED",
                )
            }
            info(
                "9.5",
                "Analyse-Worker: Validierungs-Warnungen seit Start (nur Zaehler; Label-Repair-Indikator)",
                str(cls),
            )
        check(
            f"9.3-{key}",
            f"Logs {cn} seit Start: 0 Tracebacks, 0 ERROR",
            rc == 0 and tb == 0 and not er,
            f"zeilen={len(lines)} traceback={tb} error={len(er)} http5xx={s5} heads={heads}",
        )
    r = Client(API).get("/v1/health/ready")
    check(
        "9.4",
        "Readiness /v1/health/ready healthy (db, engine, llm, pdf)",
        r.code == 200 and all(v == "healthy" for v in r.json.values()),
        f"{r.code} {r.json}",
    )


# ---------------------------------------------------------------- Abschnitt 11: Zaehlung


def synth_users():
    return f"select id from users where email like '{SYNTH_PREFIX}%'"


@section
def s11_counts():
    u = synth_users()
    cnt = {
        "users": psql(f"select count(*) from users where email like '{SYNTH_PREFIX}%'"),
        "people": psql(f"select count(*) from people where user_id in ({u})"),
        "invitations_inviter": psql(
            f"select count(*) from connection_invitations where inviter_user_id in ({u})"
        ),
        "invitations_invitee_email": psql(
            f"select count(*) from connection_invitations where invitee_email like '{SYNTH_PREFIX}%'"
        ),
        "connections": psql(
            f"select count(*) from user_connections where user_a_id in ({u}) or user_b_id in ({u})"
        ),
        "analysis_jobs": psql(
            f"select count(*) from analysis_jobs where requested_by_user_id in ({u})"
        ),
        "report_jobs": psql(f"select count(*) from report_jobs where user_id in ({u})"),
    }
    info(
        "11.1",
        "Zeilen mit synthetischem Praefix vor dem Cleanup (kumulativ, alle Laeufe)",
        json.dumps(cnt),
    )


# ---------------------------------------------------------------- Abschnitt 12: Cleanup


def delete_account(role):
    """delete-all fuer ein synthetisches Konto; True bei 204 (zwei Versuche)."""
    a = ST["acct"].get(role)
    if not a or not a.get("id"):
        return True
    for _ in range(2):
        c, r = login(role, f"{role}-cleanup")
        if r.code == 200:
            d = c.post("/v1/account/delete-all", {"password": a["password"]})
            if d.code == 204:
                return True
    return False


def s12_cleanup():
    roles = [r for r in ST["acct"] if ST["acct"][r].get("id")]
    failed = [r for r in roles if not delete_account(r)]
    check(
        "12.1",
        "delete-all fuer alle synthetischen Konten -> 204",
        not failed,
        f"konten={len(roles)} fehlgeschlagen={failed}",
    )
    if failed:
        print("!! MANUELLE BEREINIGUNG NOETIG: synthetische Konten nicht geloescht", flush=True)
        return
    try:
        left = psql(
            f"select count(*) from users where email like '{SYNTH_PREFIX}%' and deleted_at is null and is_active"
        )
        check(
            "12.2",
            "keine aktiven synthetischen Konten uebrig",
            int(left or 0) == 0,
            f"aktiv={left}",
        )
        u = synth_users()
        rest = {
            t: psql(f"select count(*) from {t} where user_id in ({u})")
            for t in ("people", "report_jobs")
        }
        check(
            "12.3",
            "keine Nutzdaten der synthetischen Konten uebrig (people/report_jobs)",
            all(v == "0" for v in rest.values()),
            str(rest),
        )
    except Exception as e:  # noqa: BLE001
        rec("12.x", "Cleanup-Verifikation Ausnahme", "FAIL", f"{type(e).__name__}: {e}")


SCOPE = [
    "Setup und Konten (synthetisch, Praefix und Domain als Konstanten)",
    "Auth: Login, Cookies, Sessions, CSRF, Logout",
    "Zwei-Konten-Journey: Einladungen LINK/CODE/EMAIL, Connection, Workspace",
    "G3: E-Mail-Verifizierung fuer Einladungen",
    "Admin: Flags, Auditlog, Rollen (CLI promote-admin im Audit-Container)",
    "LLM: Beziehungsanalysen, Report, PDF-Export und PDF-Inhaltspruefung (pypdf)",
    "Consent/IDOR/Dissolution",
    "Web-Proxy: Login, Cookies, CSRF, Origin",
    "Worker/Queue/Logs seit Start",
    "Cleanup: delete-all aller synthetischen Konten",
]
LIMITATIONS = [
    "Nur gegen den Audit-Stack: der Lauf veraendert die Audit-DB (Verifizierung, Admin-Promotion, Flag-Umschaltung mit Wiederherstellung).",
    "LLM-Qualitaet wird nur formal geprueft (Platzhalter, Laenge, Sprache); keine inhaltliche Bewertung.",
    "Die Sprachpruefung ist eine Haeufigkeitsheuristik, kein Sprachmodell.",
    "Die Evidenz ist redigiert (keine Secrets, Mails, UUID-Reste); fuer Forensik sind die Container-Logs massgeblich.",
    "delete-all entfernt Nutzdaten, laesst aber pro Konto eine anonymisierte Tombstone-Zeile in users zurueck; geprueft werden aktive Konten und Nutzdaten, nicht die Gesamtzahl der Zeilen.",
]


def build_parser():
    ap = argparse.ArgumentParser(description="NUMRA-Abnahmelauf (Audit)")
    ap.add_argument("--target", required=True, choices=("audit", "prod"))
    ap.add_argument("--target-sha", required=True, help="vollstaendige SHA des geprueften Stands")
    ap.add_argument("--api-base", required=True)
    ap.add_argument("--web-base", required=True)
    ap.add_argument("--stack-config", required=True, help="Konfig wie fuer numra-release.sh")
    ap.add_argument("--report-dir", required=True)
    ap.add_argument("--repo-dir", required=True, help="Checkout; HEAD muss --target-sha sein")
    ap.add_argument("--allow-smtp-synthetic", action="store_true")
    ap.add_argument("--skip-llm", action="store_true")
    ap.add_argument(
        "--reset-ratelimit",
        action="store_true",
        help="loescht NUR auth:register:*/auth:login:* Zaehler im Redis des Ziels",
    )
    ap.add_argument("--llm-timeout", type=int, default=600)
    ap.add_argument("--dry-run", action="store_true")
    return ap


def configure(args):
    global API, WEB
    if args.target != "audit":
        raise SystemExit(
            "VERWEIGERT: numra_acceptance.py veraendert die Datenbank und laeuft nur mit --target audit (Prod: numra_smoke.py)"
        )
    if not re.fullmatch(r"[0-9a-f]{40}", args.target_sha):
        raise SystemExit("VERWEIGERT: --target-sha muss eine vollstaendige SHA (40 Hex) sein")
    API, WEB = args.api_base.rstrip("/"), args.web_base.rstrip("/")
    for url in (API, WEB):
        Client(url)
    try:
        p = stack_config.bind(args.target, API, stack_config.load(args.stack_config))
    except stack_config.StackRefusalError as e:
        raise SystemExit(f"VERWEIGERT: {e}") from e
    args.container_prefix = p
    CONTAINERS.update(
        api=f"{p}api-1",
        pg=f"{p}postgres-1",
        redis=f"{p}redis-1",
        worker=f"{p}worker-1",
        aworker=f"{p}analysis-worker-1",
    )


def preflight(args):
    rc, out = sh(["docker", "exec", CONTAINERS["api"], "printenv", "ENVIRONMENT"])
    if rc != 0 or not out.strip():
        raise SystemExit("VERWEIGERT: ENVIRONMENT im API-Container nicht lesbar (falscher Stack?)")
    ST["env"] = out.strip()
    rc, out = sh(["git", "-C", args.repo_dir, "rev-parse", "HEAD"])
    head = out.strip()
    if rc != 0 or head != args.target_sha:
        raise SystemExit("VERWEIGERT: Checkout-HEAD != --target-sha")
    try:
        ST["mail_backend"] = stack_config.check_mail_backend(
            mail_backend(), args.allow_smtp_synthetic
        )
    except stack_config.StackRefusalError as e:
        raise SystemExit(f"VERWEIGERT: {e}") from e
    return head


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        content_checks.analyze_pdf(b"")
        configure(args)
    except content_checks.MissingDependencyError as e:
        print(f"VERWEIGERT: {e}", file=sys.stderr)
        return 2
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2
    started = dt.datetime.now(dt.UTC)
    if args.dry_run:
        DRY["on"] = True
        print(
            f"== Abnahme DRY-RUN target={args.target} sha={args.target_sha[:8]} api={API} web={WEB} prefix={args.container_prefix}"
        )
        for item in SCOPE:
            print(f"   Plan: {item}")
        print("DRY-RUN: kein HTTP-Request, kein Prozessaufruf, kein Bericht")
        return 0
    try:
        head = preflight(args)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2
    rand = secrets.token_hex(3)
    print(
        f"== Abnahme target={args.target} api={API} web={WEB} env={ST['env']} repo_head={head[:8]} run={rand}",
        flush=True,
    )
    try:
        if args.reset_ratelimit:
            for pat in ("auth:register:*", "auth:login:*"):
                sh(
                    [
                        "docker",
                        "exec",
                        CONTAINERS["redis"],
                        "sh",
                        "-c",
                        f"redis-cli --scan --pattern '{pat}' | xargs -r redis-cli del",
                    ]
                )
        s0_setup(rand)
        s1_auth(ST["env"])
        s2_journey()
        s3_g3()
        if not args.skip_llm:
            llm_start()
        s5_admin()
        if not args.skip_llm:
            llm_poll(args.llm_timeout)
            llm_eval()
        else:
            for sid in ("6", "7", "10"):
                skip(sid, "LLM-Abschnitt", "--skip-llm")
        s4_consent()
        s8_proxy()
        s9_workers(started)
        s11_counts()
    except SystemExit as e:
        rec("abort", "Abbruch", "FAIL", str(e))
    finally:
        s12_cleanup()
    return finish(args, started)


def finish(args, started):
    limitations = list(LIMITATIONS)
    if args.skip_llm:
        limitations.append("LLM-, Report- und PDF-Abschnitte wurden mit --skip-llm uebersprungen.")
    rep = ops_report.build_report(
        kind="acceptance",
        target=args.target,
        target_sha=args.target_sha,
        script="numra_acceptance.py",
        script_version=SCRIPT_VERSION,
        started=started.isoformat(timespec="seconds"),
        finished=ops_report.now_iso(),
        scope=SCOPE,
        steps=STEPS,
        limitations=limitations,
        partial=args.skip_llm,
        extra={
            "environment": ST.get("env", "unknown"),
            "container_prefix": args.container_prefix,
            "skip_llm": args.skip_llm,
            "mail_backend": ST.get("mail_backend", "unknown"),
        },
    )
    stem = f"acceptance-{args.target}-{started.strftime('%Y%m%dT%H%M%SZ')}"
    json_path, md_path = ops_report.write_report(rep, Path(args.report_dir), stem)
    s = rep["summary"]
    print(
        f"\nErgebnis {rep['result']}: PASS {s['PASS']} FAIL {s['FAIL']} SKIP {s['SKIP']} INFO {s['INFO']}"
    )
    print(f"Bericht: {md_path}\nBericht: {json_path}")
    return {"PASS": 0, "PARTIAL": 3}.get(rep["result"], 1)


if __name__ == "__main__":
    sys.exit(main())
