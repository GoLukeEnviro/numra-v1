#!/usr/bin/env python3
"""HTTP-Sonde fuer den Restore-/Rollback-Drill (nur Standardbibliothek).

Laeuft im API-Container des Drills (stdin: `docker exec -i ... python - < drill_probe.py`),
spricht 127.0.0.1:$PORT an, legt genau ein synthetisches Konto an und loescht es am Ende
immer per delete-all. Ausgabe: je Pruefung `PROBE <name> <code> <erwartet> <PASS|FAIL>`,
Exit 1 bei mindestens einem FAIL. Zugangsdaten bleiben im Prozess.
"""

import json
import os
import secrets
import sys
import urllib.error
import urllib.request

SYNTH_PREFIX = "drill-"
SYNTH_DOMAIN = "example.com"
BASE = f"http://127.0.0.1:{os.environ.get('PORT', '8000')}"
ZERO = "00000000-0000-0000-0000-000000000000"
cookies: dict[str, str] = {}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


opener = urllib.request.build_opener(NoRedirect)


def call(method, path, body=None, with_csrf=False):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if cookies:
        req.add_header("Cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()))
    if with_csrf and "numra_csrf" in cookies:
        req.add_header("x-csrf-token", cookies["numra_csrf"])
    try:
        resp = opener.open(req, timeout=15)
        status, headers = resp.status, resp.headers
    except urllib.error.HTTPError as err:
        status, headers = err.code, err.headers
    except OSError:
        return 0
    for line in headers.get_all("Set-Cookie") or []:
        name, _, rest = line.partition("=")
        value = rest.split(";", 1)[0]
        if value and "Max-Age=0" not in line:
            cookies[name.strip()] = value
        else:
            cookies.pop(name.strip(), None)
    return status


def main() -> int:
    email = f"{SYNTH_PREFIX}{secrets.token_hex(4)}@{SYNTH_DOMAIN}"
    password = secrets.token_hex(10) + "Aa1!"
    creds = {"email": email, "password": password}
    results: list[tuple[str, int, tuple[int, ...]]] = []

    def probe(name, code, expected):
        results.append((name, code, expected))

    probe("ready", call("GET", "/v1/health/ready"), (200,))
    probe("register", call("POST", "/v1/auth/register", creds), (201,))
    probe("login", call("POST", "/v1/auth/login", creds), (200,))
    probe("me", call("GET", "/v1/auth/me"), (200,))
    probe("sessions", call("GET", "/v1/auth/sessions"), (200,))
    probe("admin_flags_as_user", call("GET", "/v1/admin/flags"), (403,))
    probe("checkins_flag_gate", call("GET", f"/v1/workspaces/{ZERO}/checkins"), (401, 503))
    probe("export_list", call("GET", "/v1/exports"), (200,))
    probe(
        "delete_all_without_csrf",
        call("POST", "/v1/account/delete-all", {"password": password}),
        (403,),
    )
    cleanup = call("POST", "/v1/account/delete-all", {"password": password}, with_csrf=True)
    probe("delete_all_with_csrf", cleanup, (200, 204))
    cookies.clear()
    probe("login_after_delete", call("POST", "/v1/auth/login", creds), (401,))
    failed = 0
    for name, code, expected in results:
        ok = code in expected
        failed += not ok
        print(f"PROBE {name} {code} {'|'.join(map(str, expected))} {'PASS' if ok else 'FAIL'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
