"""Benannte Rate-Limit-Policies für die Auth-Endpunkte (Fixed Window: Anzahl/Sekunden).

Schlüsselart je Policy:
- ohne Suffix: Client-IP (vor Anmeldung, aus vertrauenswürdig ermittelter Quelle) bzw.
  Nutzer-ID (`auth:request_email_verification`, nach Anmeldung, aus der Session);
- `:target`: normalisierte Ziel-Adresse, unabhängig davon, ob ein Konto existiert
  (keine Enumeration über Limits).

Überschreibbar über `RATE_LIMIT_OVERRIDES` (JSON-Objekt `{"<policy>": "<anzahl>/<sekunden>"}`).
"""

from __future__ import annotations

__all__ = ["DEFAULT_POLICIES", "parse_policy_spec"]

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
    "auth:request_email_verification:ip": (20, 3600),
}


def parse_policy_spec(spec: str) -> tuple[int, int]:
    limit_text, separator, window_text = spec.partition("/")
    if not separator or not limit_text.isdigit() or not window_text.isdigit():
        raise ValueError("erwartet '<anzahl>/<sekunden>'")
    limit, window = int(limit_text), int(window_text)
    if limit < 1 or window < 1:
        raise ValueError("Anzahl und Fenster müssen >= 1 sein")
    return limit, window
