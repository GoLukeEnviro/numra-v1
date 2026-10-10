"""Bindung der Abnahmelaeufe an genau einen Stack und Mail-Sicherheit des Ziels.

Die Abnahmeskripte lesen dieselbe Konfigurationsdatei wie `scripts/release/numra-release.sh`
(nur als Schluessel=Wert-Zeilen, es wird nichts ausgefuehrt). Daraus folgt:

* `CONFIG_TARGET` muss zu `--target` passen (eine audit-Konfig kann nie gegen prod laufen);
* die Container-Namen leiten sich aus `PROJECT` ab (`<PROJECT>-<dienst>-1`), es gibt keinen
  frei waehlbaren Praefix, mit dem ein audit-Lauf auf Prod-Container zeigen koennte;
* `--api-base` muss auf denselben Port zeigen wie `READY_URL` der Konfiguration.
"""

from __future__ import annotations

import re
import urllib.parse
from pathlib import Path

REQUIRED_KEYS = ("CONFIG_TARGET", "PROJECT", "READY_URL")
MAIL_OK = ("disabled", "logging")


class StackRefusalError(Exception):
    """Aufruf passt nicht zum konfigurierten Stack."""


def load(path: str | Path) -> dict[str, str]:
    """Liest `KEY=value`-Zeilen (Quotes und Kommentare entfernt), ohne Shell-Auswertung."""
    values: dict[str, str] = {}
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise StackRefusalError(f"--stack-config nicht lesbar: {type(exc).__name__}") from exc
    for line in lines:
        match = re.fullmatch(r"([A-Z][A-Z0-9_]*)=(.*)", line.strip())
        if not match:
            continue
        raw = match.group(2).strip()
        if raw[:1] in ("'", '"'):
            end = raw.find(raw[0], 1)
            value = raw[1:end] if end > 0 else raw[1:]
        else:
            value = raw.split(" #", 1)[0].strip()
        values[match.group(1)] = value
    missing = [k for k in REQUIRED_KEYS if not values.get(k)]
    if missing:
        raise StackRefusalError(f"--stack-config ohne {', '.join(missing)}")
    return values


def bind(target: str, api_base: str, stack: dict[str, str]) -> str:
    """Prueft Ziel und API-Port gegen die Konfiguration; liefert den Container-Praefix."""
    if stack["CONFIG_TARGET"] != target:
        raise StackRefusalError(
            f"Stack-Konfig gehoert zu CONFIG_TARGET={stack['CONFIG_TARGET']}, "
            f"aufgerufen mit --target {target}"
        )
    api_port = urllib.parse.urlparse(api_base).port
    ready_port = urllib.parse.urlparse(stack["READY_URL"]).port
    if api_port is None or api_port != ready_port:
        raise StackRefusalError("--api-base passt nicht zum READY_URL-Port der Stack-Konfig")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", stack["PROJECT"]):
        raise StackRefusalError("PROJECT der Stack-Konfig ist kein gueltiger Projektname")
    return f"{stack['PROJECT']}-"


def check_mail_backend(backend: str, allow_smtp: bool) -> str:
    """EMAIL_BACKEND des Ziel-Containers: smtp nur mit ausdruecklicher Bestaetigung."""
    value = backend.strip() or "disabled"
    if value in MAIL_OK:
        return value
    if value == "smtp" and allow_smtp:
        return value
    raise StackRefusalError(
        f"EMAIL_BACKEND={value} im Zielcontainer: Lauf wuerde reale Mails ausloesen koennen "
        "(smtp nur mit --allow-smtp-synthetic und ausschliesslich synthetischen Adressen)"
    )
