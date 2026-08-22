"""A minimal, safe person reference embedded in other resources' list/summary
shapes (reports, relationships) so the frontend never needs a browser-only cache to
know whose data it's looking at. Mirrors `apps/web/src/lib/identity.ts`'s
`personDisplayName`: preferred name if set, else the birth name — never a
numerology-bearing field on its own.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class PersonRefOut(BaseModel):
    id: uuid.UUID
    display_name: str


def person_display_name(
    *,
    preferred_name: str | None,
    birth_first_names: str,
    birth_last_name: str,
) -> str:
    preferred = (preferred_name or "").strip()
    if preferred:
        return preferred
    return f"{birth_first_names} {birth_last_name}".strip()
