#!/usr/bin/env python3
"""Gemeinsame Berichtserzeugung fuer Release- und Abnahme-Werkzeuge (nur Standardbibliothek).

Ein Bericht besteht aus einer JSON- und einer Markdown-Datei mit Zeitstempel, Ziel, Ziel-SHA,
Skriptversion, Pruefumfang, Einzelergebnissen (PASS/FAIL/SKIP/INFO), Einschraenkungen und
Gesamtergebnis. Ein Hash allein ist kein Bericht. Alle Texte laufen durch `redact`: Secrets,
Mailadressen, UUIDs und lange Tokens verlassen den Prozess nie.

CLI:
    report.py render --records FILE --out-dir DIR --kind K --target T --target-sha SHA
        --script NAME --script-version V --started ISO [--scope-file F] [--limitations-file F]
        [--extra KEY=VALUE ...] [--dry-run]
        records: TSV je Zeile `STATUS<TAB>ID<TAB>DETAIL`.
    report.py check-smoke --report FILE --target T --sha SHA [--max-age-s N]
        Exit 0, wenn der Bericht ein echter (kein Dry-Run) PASS fuer Ziel und SHA ist.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
STATUSES = ("PASS", "FAIL", "SKIP", "INFO")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_UUID = re.compile(r"\b([0-9a-f]{8})-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
_TOKEN = re.compile(r"[A-Za-z0-9_\-]{32,}")
_SHA = re.compile(r"[0-9a-f]{40}")


def redact(
    text: object, secrets: tuple[str, ...] = (), keep_prefix: str = "", limit: int = 400
) -> str:
    """Entfernt Secrets, Mailadressen (ausser `keep_prefix`), UUID-Reste und Tokens."""
    out = str(text)
    for secret in secrets:
        if secret:
            out = out.replace(secret, "<secret>")

    def _mail(m: re.Match[str]) -> str:
        return m.group(0) if keep_prefix and m.group(0).startswith(keep_prefix) else "<email>"

    out = _EMAIL.sub(_mail, out)
    out = _UUID.sub(lambda m: m.group(1) + "..", out)
    out = _TOKEN.sub(lambda m: m.group(0) if _SHA.fullmatch(m.group(0)) else "<tok>", out)
    return out[:limit]


def now_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def summarize(steps: list[dict[str, str]]) -> dict[str, int]:
    summary = dict.fromkeys(STATUSES, 0)
    for step in steps:
        summary[step["status"]] += 1
    return summary


def build_report(
    *,
    kind: str,
    target: str,
    target_sha: str,
    script: str,
    script_version: str,
    started: str,
    finished: str,
    scope: list[str],
    steps: list[dict[str, str]],
    limitations: list[str],
    dry_run: bool = False,
    partial: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    for step in steps:
        if step["status"] not in STATUSES:
            raise ValueError(f"unbekannter Status: {step['status']}")
    summary = summarize(steps)
    result = "PASS" if summary["FAIL"] == 0 and (summary["PASS"] > 0 or dry_run) else "FAIL"
    if result == "PASS" and partial:
        result = (
            "PARTIAL"  # bewusst uebersprungene Abschnitte: nie als vollstaendige Abnahme gueltig
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "target": target,
        "target_sha": target_sha,
        "script": script,
        "script_version": script_version,
        "started": started,
        "finished": finished,
        "dry_run": dry_run,
        "result": result,
        "summary": summary,
        "scope": scope,
        "steps": steps,
        "limitations": limitations,
        "extra": extra or {},
    }


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        f"# {report['kind'].capitalize()}-Bericht: {report['script']} ({report['target']})",
        "",
        f"- Ergebnis: **{report['result']}**"
        + (" (Dry-Run, nichts mutiert)" if report["dry_run"] else ""),
        f"- Ziel: `{report['target']}`, Ziel-SHA: `{report['target_sha']}`",
        f"- Skriptversion: `{report['script_version']}`",
        f"- Zeitraum: {report['started']} bis {report['finished']} (UTC)",
        f"- Zaehlung: PASS {s['PASS']}, FAIL {s['FAIL']}, SKIP {s['SKIP']}, INFO {s['INFO']}",
        "",
        "## Pruefumfang",
        "",
    ]
    lines += [f"- {item}" for item in report["scope"]] or ["- (nicht angegeben)"]
    lines += [
        "",
        "## Einzelergebnisse",
        "",
        "| ID | Status | Pruefung | Evidenz |",
        "|---|---|---|---|",
    ]
    for step in report["steps"]:
        cells = [step["id"], step["status"], step["name"], step.get("evidence", "")]
        lines.append(
            "| " + " | ".join(c.replace("|", "/").replace("\n", " ") for c in cells) + " |"
        )
    lines += ["", "## Einschraenkungen", ""]
    lines += [f"- {item}" for item in report["limitations"]] or ["- keine bekannt"]
    if report["extra"]:
        lines += ["", "## Zusatzangaben", ""]
        lines += [f"- {k}: `{v}`" for k, v in sorted(report["extra"].items())]
    return "\n".join(lines) + "\n"


def _write_private(path: Path, content: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def write_report(report: dict[str, Any], out_dir: Path, stem: str) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    json_path, md_path = out_dir / f"{stem}.json", out_dir / f"{stem}.md"
    _write_private(json_path, json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    _write_private(md_path, render_markdown(report))
    return json_path, md_path


KNOWN_SCRIPTS = {"smoke": "numra_smoke.py", "acceptance": "numra_acceptance.py"}


def check_smoke_report(
    path: Path,
    target: str,
    sha: str,
    max_age_s: int = 3600,
    now: dt.datetime | None = None,
    kinds: tuple[str, ...] = ("smoke", "acceptance"),
    min_pass: int = 1,
    after: str | None = None,
) -> tuple[bool, str]:
    """Ist `path` ein echter, vollstaendiger Abnahmebericht fuer genau dieses Ziel und diese SHA?

    Akzeptiert werden nur Berichte der Art `kinds` (Release-, Drill- und Dry-Run-Berichte nie),
    vom passenden Skript, mit Ergebnis PASS (nicht PARTIAL), ohne uebersprungene LLM-Abschnitte,
    mit mindestens `min_pass` bestandenen Pruefungen, nicht aelter als `max_age_s` und - wenn
    `after` gesetzt ist - gestartet nach diesem Zeitpunkt (z. B. Ende des switch).
    """
    try:
        return _check_smoke_report(path, target, sha, max_age_s, now, kinds, min_pass, after)
    except (TypeError, AttributeError, KeyError, ValueError) as exc:
        return False, f"Bericht strukturell ungueltig ({type(exc).__name__})"


def _check_smoke_report(
    path: Path,
    target: str,
    sha: str,
    max_age_s: int,
    now: dt.datetime | None,
    kinds: tuple[str, ...],
    min_pass: int,
    after: str | None,
) -> tuple[bool, str]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        finished = dt.datetime.fromisoformat(report["finished"])
        started = dt.datetime.fromisoformat(report["started"])
        after_dt = dt.datetime.fromisoformat(after) if after is not None else None
        if after is not None and not after:
            raise ValueError("after leer")
    except (OSError, ValueError, KeyError) as exc:
        return False, f"Bericht oder Zeitangabe nicht lesbar: {type(exc).__name__}"
    if not isinstance(report, dict):
        return False, "Bericht ist kein JSON-Objekt"
    stamps = [finished, started] + ([after_dt] if after_dt is not None else [])
    if any(stamp.tzinfo is None for stamp in stamps):
        return False, "Zeitangaben ohne Zeitzone (naive Zeitstempel)"
    if not isinstance(report.get("summary"), dict) or not isinstance(report.get("extra"), dict):
        return False, "summary/extra fehlen oder sind kein Objekt"
    if report.get("schema_version") != SCHEMA_VERSION:
        return False, "Schema-Version unbekannt"
    kind = report.get("kind")
    if kind not in kinds:
        return (
            False,
            f"Berichtsart {kind} ist keine Abnahme fuer dieses Ziel (erlaubt: {', '.join(kinds)})",
        )
    if report.get("script") != KNOWN_SCRIPTS.get(str(kind)):
        return False, "Bericht stammt nicht vom erwarteten Abnahmeskript"
    if report.get("dry_run") is not False:
        return False, "Dry-Run-Bericht zaehlt nicht als Abnahme"
    summary = report.get("summary", {})
    if report.get("result") != "PASS" or summary.get("FAIL", 1) != 0:
        return False, f"Ergebnis nicht PASS ({report.get('result')})"
    if report.get("extra", {}).get("skip_llm") not in (None, False, "False", "false", "0"):
        return False, "Bericht mit uebersprungenen LLM-Abschnitten (skip_llm)"
    if summary.get("PASS", 0) < min_pass:
        return False, f"zu wenige bestandene Pruefungen ({summary.get('PASS', 0)} < {min_pass})"
    if report.get("target") != target:
        return False, "Ziel des Berichts passt nicht"
    if report.get("target_sha") != sha:
        return False, "Ziel-SHA des Berichts passt nicht"
    current = now or dt.datetime.now(dt.UTC)
    age = (current - finished).total_seconds()
    if age < 0 or age > max_age_s:
        return False, f"Bericht zu alt oder aus der Zukunft (alter_s={int(age)})"
    if after_dt is not None and started < after_dt:
        return False, "Bericht wurde vor dem Ende des switch gestartet"
    return True, "ok"


def _records(path: Path, secrets: tuple[str, ...] = ()) -> list[dict[str, str]]:
    steps = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        status, _, rest = line.partition("\t")
        step_id, _, detail = rest.partition("\t")
        steps.append(
            {
                "id": redact(step_id or str(number), secrets, limit=80),
                "status": status,
                "name": redact(step_id, secrets, limit=120),
                "evidence": redact(detail, secrets),
            }
        )
    return steps


def _lines(path: str | None) -> list[str]:
    return Path(path).read_text(encoding="utf-8").splitlines() if path else []


def _env_secrets(names: list[str]) -> tuple[str, ...]:
    return tuple(v for v in (os.environ.get(n, "") for n in names) if len(v) >= 4)


def _cmd_render(args: argparse.Namespace) -> int:
    secrets = _env_secrets(args.redact_env)
    extra = dict(item.split("=", 1) for item in args.extra)
    report = build_report(
        kind=args.kind,
        target=args.target,
        target_sha=args.target_sha,
        script=args.script,
        script_version=args.script_version,
        started=args.started,
        finished=now_iso(),
        scope=[redact(x, secrets, limit=300) for x in _lines(args.scope_file)],
        steps=_records(Path(args.records), secrets),
        limitations=[redact(x, secrets, limit=300) for x in _lines(args.limitations_file)],
        dry_run=args.dry_run,
        partial=args.partial,
        extra=extra,
    )
    stem = f"{args.kind}-{args.target}-{extra.get('phase', 'run')}-" + re.sub(
        r"\D", "", report["started"]
    )
    json_path, md_path = write_report(report, Path(args.out_dir), stem)
    print(f"Bericht: {md_path}")
    print(f"Bericht: {json_path}")
    return 0 if report["result"] == "PASS" else 1


def _cmd_check_smoke(args: argparse.Namespace) -> int:
    ok, reason = check_smoke_report(
        Path(args.report),
        args.target,
        args.sha,
        args.max_age_s,
        kinds=tuple(args.kinds.split(",")),
        min_pass=args.min_pass,
        after=args.after,
    )
    print(("OK: " if ok else "ABGELEHNT: ") + reason)
    return 0 if ok else 1


def _cmd_redact(args: argparse.Namespace) -> int:
    secrets = _env_secrets(args.redact_env)
    for line in sys.stdin:
        print(redact(line.rstrip("\n"), secrets, limit=2000))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    render = sub.add_parser("render")
    for name in ("records", "out-dir", "kind", "target", "target-sha", "script", "script-version"):
        render.add_argument(f"--{name}", required=True)
    render.add_argument("--started", required=True)
    render.add_argument("--scope-file")
    render.add_argument("--limitations-file")
    render.add_argument("--extra", action="append", default=[], metavar="KEY=VALUE")
    render.add_argument("--dry-run", action="store_true")
    render.add_argument("--partial", action="store_true")
    render.add_argument("--redact-env", action="append", default=[], metavar="VAR")
    render.set_defaults(func=_cmd_render)
    smoke = sub.add_parser("check-smoke")
    smoke.add_argument("--report", required=True)
    smoke.add_argument("--target", required=True)
    smoke.add_argument("--sha", required=True)
    smoke.add_argument("--max-age-s", type=int, default=3600)
    smoke.add_argument("--kinds", default="smoke,acceptance")
    smoke.add_argument("--min-pass", type=int, default=1)
    smoke.add_argument(
        "--after", default=None, help="ISO-Zeitpunkt; Bericht muss danach gestartet sein"
    )
    smoke.set_defaults(func=_cmd_check_smoke)
    redact_cmd = sub.add_parser("redact")
    redact_cmd.add_argument("--redact-env", action="append", default=[], metavar="VAR")
    redact_cmd.set_defaults(func=_cmd_redact)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
