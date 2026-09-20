"""Deterministische Textlaengen-Formung fuer den Mock-Reportpfad.

Nicht als Ersatz fuer echte Generierung gedacht: der `MockLLMProvider` ist der
netzwerkfreie Fallback fuer Tests, CI und lokale Entwicklung, und der Report-Pipeline
braucht trotzdem Abschnitte in realistischer Laenge (der Linter prueft jede Sektion
gegen ihre Zielwortzahl und gegen doppelte Absaetze). Echte Generierung macht der
konfigurierte Provider.

Zwei Eigenschaften sind bewusst:

* **Ganze Saetze.** Es wird nie mitten im Satz abgeschnitten -- der Text ist auch im
  Fallback lesbare Prosa, keine Wortkette.
* **Jeder Absatz traegt eine eigene Ueberschrift.** `paragraph_prefixes` sind
  abschnittsspezifische, menschenlesbare Einleitungen (der Aufrufer setzt den
  Abschnittstitel ein). Damit kann ein Absatz aus zwei verschiedenen Reportabschnitten
  niemals identisch sein, was der globale Linter verlangt
  (`DuplicateParagraphDetection`).
"""

from __future__ import annotations

__all__ = ["deterministic_prose"]

#: Sicherheitsnetz: CUSTOM-Reports duerfen beliebige Zielwortzahlen verlangen.
_MAX_PARAGRAPHS = 400

#: Satzanzahl je Absatz, zyklisch. Zusammen mit der Laenge von `paragraph_prefixes`
#: und der Groesse des Satzpools bestimmt dieses Muster, nach wie vielen Absaetzen
#: sich ein Absatz theoretisch wiederholen koennte (kleinstes gemeinsames Vielfaches,
#: praktisch >= 60 Absaetze) -- deutlich mehr, als selbst ein ULTIMATE-Abschnitt hat.
_SENTENCES_PER_PARAGRAPH = (1, 2, 3, 2, 1)

#: Minimale Absatzlaenge. Haelt die Zahl der Absaetze klein genug, dass das
#: Wiederholungsintervall oben nicht erreicht wird.
_MIN_PARAGRAPH_WORDS = 60

#: Obergrenze fuer einen Absatz. 60--140 Woerter lesen sich als Absatz; alles darueber
#: wird zur Textwand.
_MAX_PARAGRAPH_WORDS = 140


def deterministic_prose(
    *,
    sentences: tuple[str, ...],
    target_word_count: int,
    paragraph_prefixes: tuple[str, ...] = (),
) -> str:
    """Deterministische, lesbare Prosa von mindestens ``target_word_count`` Woertern.

    ``sentences`` sind fertige Saetze (Satz fuer Satz aus dem Pool, zyklisch), die zu
    Absaetzen gebuendelt und jeweils mit einem Element aus ``paragraph_prefixes``
    eingeleitet werden (zyklisch, in Reihenfolge). Die Zielwortzahl wird nie
    unterschritten; ueberschritten wird sie nur um den letzten Satz eines Absatzes.
    """
    pool = tuple(dict.fromkeys(sentence.strip() for sentence in sentences if sentence.strip()))
    if not pool or target_word_count <= 0:
        return ""

    paragraph_target = min(_MAX_PARAGRAPH_WORDS, max(_MIN_PARAGRAPH_WORDS, target_word_count // 8))
    paragraphs: list[str] = []
    words = 0
    cursor = 0

    while words < target_word_count and len(paragraphs) < _MAX_PARAGRAPHS:
        wanted = _SENTENCES_PER_PARAGRAPH[len(paragraphs) % len(_SENTENCES_PER_PARAGRAPH)]
        chunk: list[str] = []
        chunk_words = 0
        while len(chunk) < wanted or (
            chunk_words < paragraph_target and len(chunk) < len(pool) * 2
        ):
            sentence = pool[cursor % len(pool)]
            cursor += 1
            chunk.append(sentence)
            chunk_words += len(sentence.split())

        prefix = (
            paragraph_prefixes[len(paragraphs) % len(paragraph_prefixes)]
            if paragraph_prefixes
            else ""
        )
        paragraph = " ".join(part for part in (prefix, " ".join(chunk)) if part)
        paragraphs.append(paragraph)
        words += len(paragraph.split())

    return "\n\n".join(paragraphs)
