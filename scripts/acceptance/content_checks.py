"""Inhaltspruefungen fuer Abnahmelaeufe: Platzhalter-Treffer, Sprache, PDF-Inhalt.

Ersetzt den frueheren PDF-SKIP ("weder pdftotext noch Bibliothek vorhanden") durch eine
reproduzierbare Pruefung mit pypdf (siehe requirements.txt): Seitenzahl, extrahierbarer Text,
deutsche Sprache und null Platzhalter-/Token-Treffer wie `[a:`, `{{` oder `{name}`.
Reine Funktionen ohne Netz und ohne Docker, damit sie einzeln testbar sind.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

MIN_PDF_BYTES = 20480  # einheitlich fuer Smoke und Acceptance

PLACEHOLDERS = [
    r"\[[a-z_]+:",
    r"\{\{",
    r"\}\}",
    r"\{[a-z_]+\}",
    r"<[a-z]+_[a-z_]+>",
    r"%\(",
]
SCAFFOLDING = [r"\[[ab]\s*:", r"profile_fact", r"metric:"]
DE = set(
    (  # noqa: SIM905
        "der die das und ist nicht mit ein eine für von zu den auf sich im es auch wie dem des "
        "dass sie wir ihr bei oder aber wird werden kann können mehr als nach um aus durch einen "
        "einer ihre ihren seine ihm ihn man nur noch sehr wenn dies diese diesen"
    ).split()
)
EN = set(
    (  # noqa: SIM905
        "the and is not with a an for of to on in it also how that you we your are or but will "
        "can more as from by his her them only still very when this these"
    ).split()
)
WORD = re.compile(r"[A-Za-zÄÖÜäöüß]+")


class MissingDependencyError(RuntimeError):
    """pypdf fehlt: Installation per `pip install -r scripts/acceptance/requirements.txt`."""


def flatten_strings(obj: object, out: list[str] | None = None) -> list[str]:
    out = [] if out is None else out
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for value in obj.values():
            flatten_strings(value, out)
    elif isinstance(obj, list):
        for value in obj:
            flatten_strings(value, out)
    return out


def placeholder_hits(strings: list[str], patterns: list[str] | None = None) -> list[str]:
    hits = []
    for text in strings:
        for pattern in patterns or PLACEHOLDERS:
            match = re.search(pattern, text)
            if match:
                context = text[max(0, match.start() - 10) : match.end() + 14]
                hits.append(f"{pattern}->'{context}'")
    return hits


def language_ratios(text: str) -> tuple[int, float, float]:
    tokens = WORD.findall(text.lower())
    total = max(1, len(tokens))
    de = sum(token in DE for token in tokens) / total
    en = sum(token in EN for token in tokens) / total
    return len(tokens), round(de, 3), round(en, 3)


def text_quality(obj: object) -> dict[str, object]:
    """Platzhalter, Laenge und Sprache fuer beliebig verschachtelte JSON-Strukturen."""
    strings = flatten_strings(obj)
    prose = [s for s in strings if len(s.split()) >= 5]
    text = " ".join(prose)
    words, de, en = language_ratios(text)
    return {
        "hits": placeholder_hits(strings),
        "chars": len(text),
        "words": words,
        "de": de,
        "en": en,
        "empty_strings": sum(1 for s in strings if not s.strip()),
        "prose_segments": len(prose),
        "strings": len(strings),
    }


@dataclass
class PdfAnalysis:
    pages: int = 0
    text: str = ""
    words: int = 0
    de: float = 0.0
    en: float = 0.0
    hits: list[str] = field(default_factory=list)
    error: str = ""


def analyze_pdf(data: bytes) -> PdfAnalysis:
    """Liest das PDF mit pypdf; jeder Lesefehler landet mit spezifischem Text in `error`."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise MissingDependencyError(
            "pypdf fehlt: pip install -r scripts/acceptance/requirements.txt"
        ) from exc
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            return PdfAnalysis(error="PDF ist verschluesselt")
        pages = len(reader.pages)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:  # noqa: BLE001 - pypdf wirft je nach Defekt sehr unterschiedliche Typen
        return PdfAnalysis(error=f"PDF nicht lesbar ({type(exc).__name__})")
    words, de, en = language_ratios(text)
    hits = placeholder_hits([text], PLACEHOLDERS + SCAFFOLDING)
    return PdfAnalysis(pages=pages, text=text, words=words, de=de, en=en, hits=hits)


def evaluate_pdf(
    result: PdfAnalysis, min_pages: int = 1, max_pages: int = 200, min_words: int = 60
) -> list[tuple[str, str, bool, str]]:
    """Liefert (id-suffix, name, bestanden, evidenz) je Pruefung; Evidenz ohne Dokumenttext."""
    if result.error:
        return [("9", "PDF lesbar (pypdf)", False, f"Lesefehler: {result.error}")]
    return [
        (
            "9",
            f"PDF Seitenzahl {min_pages}..{max_pages}",
            min_pages <= result.pages <= max_pages,
            f"pages={result.pages}",
        ),
        (
            "10a",
            f"PDF-Text extrahierbar (>= {min_words} Woerter)",
            result.words >= min_words,
            f"words={result.words}" + (" (kein Text: Bild-PDF?)" if result.words == 0 else ""),
        ),
        (
            "10b",
            "PDF-Text deutsch",
            result.de >= 0.08 and result.de > 2 * result.en,
            f"de={result.de} en={result.en}",
        ),
        (
            "10c",
            "PDF-Text ohne Platzhalter-/Token-Treffer",
            not result.hits,
            f"treffer={len(result.hits)} {result.hits[:3]}",
        ),
    ]
