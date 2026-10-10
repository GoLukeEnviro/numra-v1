"""Benannte Rate-Limit-Policies für die Auth-Endpunkte (Fixed Window: Anzahl/Sekunden).

Schlüsselart je Policy:
- ohne Suffix: Client-IP (vor Anmeldung, aus vertrauenswürdig ermittelter Quelle) bzw.
  Nutzer-ID (`auth:request_email_verification`, nach Anmeldung, aus der Session);
- `:target`: normalisierte Ziel-Adresse, unabhängig davon, ob ein Konto existiert
  (keine Enumeration über Limits). `auth:login:target` reserviert den Versuch atomar vor der
  Passwortprüfung und wird bei Erfolg zurückgesetzt (es sammeln sich nur Fehlversuche);
  alle anderen Zähler zählen jeden Versuch.

Überschreibbar über `RATE_LIMIT_OVERRIDES` (JSON-Objekt `{"<policy>": "<anzahl>/<sekunden>"}`).
"""

from __future__ import annotations

__all__ = ["DEFAULT_POLICIES", "MAX_LIMIT", "MAX_WINDOW_SECONDS", "parse_policy_spec"]

#: Obergrenzen für Overrides: ein Tippfehler (`999999999/1`) darf ein Limit nicht faktisch
#: abschalten, ein Fenster nicht über eine Woche hinaus verlängern.
MAX_LIMIT = 10_000
MAX_WINDOW_SECONDS = 7 * 24 * 3600

#: policy -> (limit, window_seconds)
DEFAULT_POLICIES: dict[str, tuple[int, int]] = {
    "auth:login": (10, 60),
    "auth:login:target": (20, 900),
    "auth:mobile-login": (10, 60),
    "auth:register": (5, 3600),
    "auth:register:target": (3, 3600),
    "auth:forgot_password": (5, 3600),
    "auth:forgot_password:target": (3, 3600),
    "auth:reset_password": (10, 3600),
    "auth:verify_email": (10, 3600),
    "auth:request_email_verification": (5, 3600),
    "auth:request_email_verification:target": (5, 3600),
}


def _is_ascii_number(text: str) -> bool:
    return text.isascii() and text.isdigit()


def parse_policy_spec(spec: str) -> tuple[int, int]:
    limit_text, separator, window_text = spec.partition("/")
    if not separator or not _is_ascii_number(limit_text) or not _is_ascii_number(window_text):
        raise ValueError("erwartet '<anzahl>/<sekunden>'")
    limit, window = int(limit_text), int(window_text)
    if not (1 <= limit <= MAX_LIMIT and 1 <= window <= MAX_WINDOW_SECONDS):
        raise ValueError(
            f"Anzahl muss 1..{MAX_LIMIT} und Fenster 1..{MAX_WINDOW_SECONDS} Sekunden sein"
        )
    return limit, window
