from __future__ import annotations

import re
import unicodedata

from numra_numerology.models.errors import NormalizationUnsupportedScript
from numra_numerology.models.profile import NameNormalization

#: Explicit German replacements — applied AFTER uppercasing. Python's str.upper() already
#: turns "ß" into "SS" and leaves "ä/ö/ü" as "Ä/Ö/Ü" (umlaut retained), so this map handles
#: the umlaut-stripping (never AE/OE/UE — that would be a MAJOR canon version change) and
#: the capital-sharp-s edge case ("ẞ", U+1E9E) which str.upper() does not rewrite.
GERMAN_REPLACEMENTS: dict[str, str] = {
    "Ä": "A",
    "Ö": "O",
    "Ü": "U",
    "ß": "SS",
    "ẞ": "SS",
}

#: Tokenization separators: whitespace + hyphen-minus, U+2010 hyphen, U+2011 non-breaking
#: hyphen, en dash, em dash, apostrophe, U+2019 right single quotation mark.
_SEPARATOR_CHARS = " \t\n\r-‐‑–—'’"
_SEPARATOR_PATTERN = re.compile(f"[{re.escape(_SEPARATOR_CHARS)}]+")

_VALID_NAME_RE = re.compile(r"^[A-Z]*$")


def _strip_combining_marks(text: str) -> str:
    """NFD-decompose and drop combining diacritical marks (Unicode category Mn), folding
    e.g. É/È/Ê -> E, Á/À -> A, Ñ -> N, Ç -> C."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _strip_other_punctuation(text: str) -> str:
    """Typographic punctuation other than the declared tokenization separators is removed
    before component formation. Digits and unsupported-script letters are left untouched
    here — they are rejected explicitly by the A-Z validation step below, never silently
    dropped (canon-spec.md §3, §20)."""
    return "".join(
        ch
        for ch in text
        if not (unicodedata.category(ch).startswith("P") and ch not in _SEPARATOR_CHARS)
    )


def normalize_name(raw: str) -> NameNormalization:
    """Run the full NUMRA name-normalization pipeline (canon-spec.md §3).

    Raises:
        NormalizationUnsupportedScript: if any character survives outside A-Z.
    """
    original = raw
    text = unicodedata.normalize("NFC", raw).strip().upper()

    for source, target in GERMAN_REPLACEMENTS.items():
        text = text.replace(source, target)

    text = _strip_combining_marks(text)
    text = _strip_other_punctuation(text)

    raw_components = _SEPARATOR_PATTERN.split(text)
    components = tuple(component for component in raw_components if component)

    calculation_string = "".join(components)

    if not _VALID_NAME_RE.match(calculation_string):
        remaining = "".join(sorted({ch for ch in calculation_string if not ("A" <= ch <= "Z")}))
        raise NormalizationUnsupportedScript(original=original, remaining=remaining)

    return NameNormalization(
        original=original,
        components=components,
        calculation_string=calculation_string,
    )
