"""PWA-07 (#125) -- der strukturierte Kontodatenexport.

Was hier entsteht, ist *kein* Report-Rendering, sondern eine Auskunft ueber das Konto
selbst: ein JSON-Dokument mit den dokumentierten Kategorien aus
`docs/audits/2026-09-20-pwa-07-account-export.md` (Format `avenyth.account-export`,
Version 1.0).

Drei Eigenschaften sind bewusst und werden von Tests gehalten:

* **Stabile Feldnamen.** Jede Kategorie ist immer vorhanden -- ein leeres Konto
  bekommt leere Listen, keine fehlenden Schluessel. Das Dokument traegt ausserdem
  `format`, `format_version`, den Erzeugungszeitpunkt und `counts` (Anzahl Datensaetze
  je Kategorie), damit ein Konsument die Vollstaendigkeit pruefen kann, ohne das ganze
  Dokument zu durchsuchen.
* **Streaming statt Sammeln.** Das Dokument wird Kategorie fuer Kategorie geschrieben
  und ausgeliefert (`StreamingResponse`). Der Speicherbedarf haengt damit an der
  groessten Einzelkategorie, nicht an der Groesse des Kontos -- ein Konto mit
  zehntausenden Life-Tracking-Eintraegen laeuft nicht in einen Speicherfehler.
* **Nur das eigene Konto.** Jede Abfrage ist auf `user_id` bzw. die daraus abgeleiteten
  Zeilenmengen eingeschraenkt; die Fremdsicht ist der Modul-Docstring von
  `repositories/account_export.py`.

**Session-Eigentum (nicht wegoptimieren):** der Generator oeffnet seine eigene
`AsyncSession` aus dem `sessionmaker` und schliesst sie in einem `async with`. Er darf
*keine* request-gebundene Session (`Depends(get_db, scope="function")`) benutzen:
FastAPI schliesst funktionsgebundene Dependencies in `fastapi_function_astack`, und
zwar **bevor** `await response(...)` den Body streamt (fastapi/routing.py). Die
Generator-Abfragen wuerden danach auf einer bereits geschlossenen Session laufen, die
sich still eine neue Verbindung nimmt, deren Transaktion nie committet wird -- Ergebnis
ist eine "idle in transaction"-Verbindung, die Tabellen-Locks haelt. Genau das ist beim
ersten Lauf dieser Route passiert.
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from collections.abc import AsyncIterator, Callable
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from numra_api.models import User
from numra_api.repositories import account_export as export_repo

#: `format` ist der stabile Anker fuer Konsumenten -- eine Aenderung an der Struktur
#: erhoeht `format_version`, nicht `format`.
FORMAT = "avenyth.account-export"
FORMAT_VERSION = "1.0"

#: Dateiname: `<praefix>-<UTC-Zeitstempel>.json`. Das Muster ist stabil, der
#: Zeitstempel macht zwei Downloads unterscheidbar (und ist derselbe Wert wie
#: `generated_at`).
FILENAME_PREFIX = "avenyth-account-export"
_TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"


def export_filename(now: dt.datetime) -> str:
    return f"{FILENAME_PREFIX}-{now.astimezone(dt.UTC).strftime(_TIMESTAMP_FORMAT)}.json"


def _fallback(value: Any) -> str:
    """JSON-Renderer fuer die Typen, die aus der DB kommen und kein natives
    JSON-Pendant haben. `StrEnum`-Werte sind bereits `str` und landen hier nie."""
    if isinstance(value, dt.datetime):
        return value.astimezone(dt.UTC).isoformat() if value.tzinfo else value.isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"{type(value).__name__} ist nicht exportierbar")


async def _account_section(db: AsyncSession, *, user: User) -> dict[str, Any]:
    """Das Konto selbst: Identitaet, Rolle, Verifikations- und Loeschzustand sowie der
    effektive Entitlement-Satz. Passwort-Hash und Sitzungen stehen hier bewusst nicht.
    """
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name_override,
        "role": user.role,
        "is_active": user.is_active,
        "email_verified_at": user.email_verified_at,
        "created_at": user.created_at,
        # Der Soft-Delete-Zustand als eigenes Feld: ein Konto kann sich nicht im
        # geloeschten Zustand exportieren (der Login-Gate blockiert das), aber ein
        # Empfaenger des Dokuments soll den Zustand unterscheiden koennen, ohne
        # `deleted_at` selbst interpretieren zu muessen.
        "deletion": {
            "status": "deleted" if user.deleted_at is not None else "active",
            "deleted_at": user.deleted_at,
        },
        "entitlements": await export_repo.load_entitlements(db, user_id=user.id),
    }


async def _profiles_section(db: AsyncSession, *, user: User) -> list[dict[str, Any]]:
    return await export_repo.load_profiles(db, user_id=user.id)


async def _personal_workspace_section(db: AsyncSession, *, user: User) -> dict[str, Any]:
    return await export_repo.load_personal_workspace(db, user_id=user.id)


async def _relationships_section(db: AsyncSession, *, user: User) -> dict[str, Any]:
    return await export_repo.load_standalone_relationships(db, user_id=user.id)


async def _workspaces_section(db: AsyncSession, *, user: User) -> list[dict[str, Any]]:
    return await export_repo.load_workspaces(db, user_id=user.id)


async def _reports_section(db: AsyncSession, *, user: User) -> dict[str, Any]:
    return await export_repo.load_reports(db, user_id=user.id)


async def _copilot_section(db: AsyncSession, *, user: User) -> dict[str, Any]:
    return await export_repo.load_personal_copilot(db, user_id=user.id)


#: Reihenfolge = Reihenfolge im Dokument. Neue Kategorien werden hier ergaenzt; die
#: Tests in `apps/api/tests/integration/test_account_export.py` halten die Liste gegen
#: das dokumentierte Format.
_SECTIONS: tuple[tuple[str, Callable[..., Any]], ...] = (
    ("account", _account_section),
    ("profiles", _profiles_section),
    ("personal_workspace", _personal_workspace_section),
    ("relationships", _relationships_section),
    ("workspaces", _workspaces_section),
    ("reports", _reports_section),
    ("copilot", _copilot_section),
)

#: Die Kategorien des Formats, in Dokumentreihenfolge -- von aussen pruefbar, damit ein
#: Test nicht eine zweite, driftende Liste fuehren muss.
SECTION_NAMES: tuple[str, ...] = tuple(name for name, _ in _SECTIONS)


def _collect_counts(prefix: str, value: Any, out: dict[str, int]) -> None:
    """Zaehlt Datensaetze je Liste im Dokument (Pfad -> Anzahl). `counts` macht die
    "leerer Bereich ist korrekt dargestellt"-Zusage pruefbar, ohne dass ein Test jede
    Kategorie einzeln kennen muss."""
    if isinstance(value, list):
        out[prefix] = len(value)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _collect_counts(f"{prefix}.{key}" if prefix else key, item, out)


async def iter_account_export(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    user: User,
    now: dt.datetime | None = None,
) -> AsyncIterator[str]:
    """Erzeugt das Export-Dokument als Folge von JSON-Textstuecken.

    Alle Kategorien werden im Voraus *nicht* geladen: erst wird eine Kategorie
    abgefragt, dann sofort geschrieben und wieder verworfen. Das ist der Unterschied
    zwischen einem Export, der bei grossen Konten funktioniert, und einem, der das
    ganze Konto gleichzeitig im RAM haelt.

    Die Session gehoert diesem Generator (siehe Modul-Docstring): sie wird hier
    geoeffnet und hier geschlossen, egal ob der Stream zu Ende laeuft oder der Client
    vorher abbricht.
    """
    generated_at = (now or dt.datetime.now(dt.UTC)).astimezone(dt.UTC)
    yield "{"
    yield f'"format":{json.dumps(FORMAT)}'
    yield f',"format_version":{json.dumps(FORMAT_VERSION)}'
    yield f',"generated_at":{json.dumps(generated_at.isoformat())}'

    counts: dict[str, int] = {}
    async with sessionmaker() as db:
        for name, loader in _SECTIONS:
            payload = await loader(db, user=user)
            _collect_counts(name, payload, counts)
            rendered = json.dumps(payload, default=_fallback, sort_keys=True, ensure_ascii=False)
            yield f',"{name}":{rendered}'

    yield f',"counts":{json.dumps(counts, sort_keys=True)}'
    yield "}"
