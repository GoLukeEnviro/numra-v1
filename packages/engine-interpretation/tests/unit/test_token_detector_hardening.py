"""Haertung des Token-Detektors: Restluecken, Grammatik, Gegenproben, Laufzeit.

Bekannte Restluecken nach PR #308/#310, hier zuerst reproduziert (rot) und dann
geschlossen:

* Look-alike-Zeichen, die weder NFKD noch die alte Tabelle falten (``\u0261`` und weitere
  Latin-/Cyrillic-/Greek-Zeichen) innerhalb von Token-Bezeichnern und Markern;
* Steuer- und Fuellzeichen (``\u3164``, Hangul-Filler, ``\u2800``, C0/C1, Private Use) und
  BiDi-Steuerzeichen mitten in einem Marker;
* ``{0}``, ``{name!r}``, ``{:>10}`` und weitere ``str.format``-Felder im lockeren Modus;
* ``[a:foo]`` mit unbekannter ID ohne Unterstrich im strengen Modus.

Die Gegenproben (internationaler Text, Prosa mit Klammern) und die Laufzeitgrenzen stehen
im selben Modul, damit jede Verschaerfung sofort gegen ihre False-Positive-Kosten laeuft.
"""

from __future__ import annotations

import re
import time
import unicodedata

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from numra_interpretation.llm.rendering_guard import (
    MAX_CHECKED_TEXT_CHARS,
    OVERSIZE_TOKEN,
    PROMPT_SCAFFOLDING_MARKERS,
    _find_in_canonical_form,
    canonical_for_check,
    contains_prompt_scaffolding,
    find_unresolved_template_token,
    find_unresolved_token_in_payload,
)

pytestmark = pytest.mark.unit

_BOTH_MODES = pytest.mark.parametrize("strict_braces", [True, False])

# --------------------------------------------------------------------------- Look-alikes

#: Look-alike -> das lateinische Kleinbuchstaben-Zeichen, das es vortaeuscht.
_LOOKALIKES = {
    "\u0261": "g",  # ɡ LATIN SMALL LETTER SCRIPT G (der gemeldete Fall)
    "\u0251": "a",  # ɑ
    "\u0131": "i",  # ı dotless i
    "\u0237": "j",  # ȷ dotless j
    "\u0269": "i",  # ɩ
    "\u1d00": "a",  # ᴀ small capital
    "\u0299": "b",  # ʙ
    "\u1d04": "c",  # ᴄ
    "\u1d05": "d",  # ᴅ
    "\u1d07": "e",  # ᴇ
    "\u0262": "g",  # ɢ
    "\u029c": "h",  # ʜ
    "\u026a": "i",  # ɪ
    "\u1d0a": "j",  # ᴊ
    "\u1d0b": "k",  # ᴋ
    "\u029f": "l",  # ʟ
    "\u1d0d": "m",  # ᴍ
    "\u0274": "n",  # ɴ
    "\u1d0f": "o",  # ᴏ
    "\u1d18": "p",  # ᴘ
    "\u0280": "r",  # ʀ
    "\ua731": "s",  # ꜱ
    "\u1d1b": "t",  # ᴛ
    "\u1d1c": "u",  # ᴜ
    "\u1d20": "v",  # ᴠ
    "\u1d21": "w",  # ᴡ
    "\u028f": "y",  # ʏ
    "\u1d22": "z",  # ᴢ
    "\u00f8": "o",  # ø
    "\u0142": "l",  # ł
    "\u0111": "d",  # đ
    "\u0192": "f",  # ƒ
    "\u0127": "h",  # ħ
    "\u0268": "i",  # ɨ
    "\u0180": "b",  # ƀ
    "\u04bb": "h",  # һ CYRILLIC SMALL LETTER SHHA
    "\u051b": "q",  # ԛ CYRILLIC SMALL LETTER QA
    "\u050d": "g",  # ԍ CYRILLIC SMALL LETTER KOMI SJE
    "\u0475": "v",  # ѵ CYRILLIC SMALL LETTER IZHITSA
    "\u04af": "y",  # ү CYRILLIC SMALL LETTER STRAIGHT U
    "\u0455": "s",  # ѕ (war schon in der alten Tabelle)
    "\u03f2": "c",  # ϲ GREEK LUNATE SIGMA
    "\u03f3": "j",  # ϳ GREEK YOT
    "\u0461": "w",  # ѡ CYRILLIC OMEGA
    "\u03c7": "x",  # χ GREEK CHI
}


def _marker_for(letter: str) -> str | None:
    return next((m for m in PROMPT_SCAFFOLDING_MARKERS if letter in m), None)


@_BOTH_MODES
@pytest.mark.parametrize(("lookalike", "letter"), sorted(_LOOKALIKES.items()))
def test_lookalike_in_a_label_identifier_is_folded(lookalike, letter, strict_braces) -> None:
    assert canonical_for_check(lookalike) == letter
    assert find_unresolved_template_token(
        f"Satz [a:id_{lookalike}] Ende.", strict_braces=strict_braces
    )


@_BOTH_MODES
@pytest.mark.parametrize(
    ("lookalike", "letter"),
    sorted((char, letter) for char, letter in _LOOKALIKES.items() if _marker_for(letter)),
)
def test_lookalike_in_a_scaffolding_marker_is_folded(lookalike, letter, strict_braces) -> None:
    marker = _marker_for(letter)
    assert marker is not None
    forged = marker.replace(letter, lookalike, 1)
    assert forged != marker
    assert find_unresolved_template_token(f"Satz {forged} Ende.", strict_braces=strict_braces)


def _expected_latin_letter(char: str) -> str | None:
    """Welchen lateinischen Buchstaben ein Zeichen laut seinem Unicode-Namen vortaeuscht."""
    name = unicodedata.name(char, "")
    if any(part in name for part in ("WITH SMALL LETTER", "MIDDLE DOT", "RIGHT HALF RING")):
        return None  # Digraphen (ǅ), ŀ und ẚ zerfallen unter NFKD in mehrere Zeichen
    for pattern in (
        r"^LATIN (?:SMALL|CAPITAL) LETTER ([A-Z]) WITH ",
        r"^LATIN SMALL LETTER SCRIPT ([A-Z])$",
        r"^LATIN LETTER SMALL CAPITAL ([A-Z])$",
        r"^LATIN SMALL LETTER DOTLESS ([IJ])$",
    ):
        match = re.match(pattern, name)
        if match:
            return match.group(1).lower()
    return None


def test_every_named_latin_lookalike_in_unicode_is_folded() -> None:
    """Erschoepfender Scan ueber ganz Unicode statt einer Handliste: jedes Zeichen, dessen
    Name es als Variante genau eines lateinischen Buchstabens ausweist (Strich, Haken,
    Schwanz, Kapitaelchen, Schreibschrift-g, punktloses i/j), faltet in der Pruefansicht
    auf diesen Buchstaben."""
    unfolded = []
    checked = 0
    for codepoint in range(0x110000):
        char = chr(codepoint)
        expected = _expected_latin_letter(char)
        if expected is None:
            continue
        checked += 1
        if canonical_for_check(char) != expected:
            unfolded.append((f"U+{codepoint:04X}", unicodedata.name(char)))
    assert checked > 500
    assert not unfolded, unfolded[:20]


@_BOTH_MODES
@pytest.mark.parametrize(
    "text",
    (
        "Satz \u2774\u2774metric:a:life_path\u2775\u2775 mit Dingbat-Klammern.",
        "Satz \u27e6a:life_path\u27e7 mit mathematischen Klammern.",
        "Satz \u3010a:life_path\u3011 mit CJK-Klammern.",
        "Satz [a\ua789life_path] mit Modifier-Doppelpunkt.",
        "Satz [a\u02d0life_path] mit Dreiecks-Doppelpunkt.",
        "Satz [a\u2236life_path] mit Verhaeltnis-Doppelpunkt.",
        "Satz [a:life\u02cdpath] mit tiefem Makron statt Unterstrich.",
        "Satz [a:pinnacle_\u0661] mit arabisch-indischer Ziffer.",
        "Satz [a:challenge_\uff14] mit Vollbreiten-Ziffer.",
        "Satz \u27e8partner_a\u27e9 mit spitzen Klammern.",
    ),
)
def test_bracket_colon_underscore_and_digit_lookalikes_are_folded(text, strict_braces) -> None:
    assert find_unresolved_template_token(text, strict_braces=strict_braces)


# --------------------------------------------------------------------------- Steuerzeichen

_INVISIBLES = (
    "\x00",
    "\x07",
    "\x1b",
    "\x1c",
    "\x7f",
    "\x80",
    "\x85",
    "\x9f",
    "\u3164",  # HANGUL FILLER
    "\u115f",
    "\u1160",
    "\uffa0",
    "\u2800",  # BRAILLE PATTERN BLANK
    "\u200b",
    "\u200c",
    "\u200d",
    "\u2060",
    "\u2062",
    "\ufeff",
    "\u00ad",
    "\u180e",
    "\u202a",  # BiDi
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
    "\u200e",
    "\u200f",
    "\u061c",
    "\u034f",
    "\ufe0f",
    "\ue000",  # Private Use
    "\U000e0041",  # Tag
)

_TOKEN_FORMS = (
    "[profile_fact:a:life_path]",
    "[knowledge:attitude]",
    "[system]",
    "[user_instructions]",
    "[a:life_path]",
    "[b:foo_bar]",
    "{{metric:a:life_path}}",
    "{partner_a}",
    "<partner_a>",
    "%(partner_a)s",
    "{0}",
    "{name!r}",
)


@_BOTH_MODES
@pytest.mark.parametrize("invisible", _INVISIBLES)
@pytest.mark.parametrize("form", _TOKEN_FORMS)
def test_an_invisible_character_at_any_position_never_hides_a_token(
    form, invisible, strict_braces
) -> None:
    for position in range(len(form) + 1):
        forged = form[:position] + invisible + form[position:]
        text = f"Ein Satz {forged} geht weiter."
        assert find_unresolved_template_token(text, strict_braces=strict_braces), (
            f"verdeckt bei Position {position}"
        )


@_BOTH_MODES
def test_many_invisible_characters_in_one_marker_are_all_ignored(strict_braces) -> None:
    forged = "[" + "\u3164\u200b".join("profile_fact") + ":a:life_path]"
    assert find_unresolved_template_token(forged, strict_braces=strict_braces)
    assert contains_prompt_scaffolding(forged)


def test_whitespace_controls_stay_whitespace_in_the_check_view() -> None:
    assert canonical_for_check("[a\n:\tlife_path]") == "[a\n:\tlife_path]"
    assert find_unresolved_template_token("Satz [a\n:\tlife_path] Ende.")


# --------------------------------------------------------------------------- Format-Felder

_FORMAT_FIELDS = (
    "{0}",
    "{12}",
    "{name!r}",
    "{name!s}",
    "{!r}",
    "{0!a}",
    "{0:>10}",
    "{0:08.3f}",
    "{:.2f}",
    "{:>10}",
    "{:,}",
    "{:^20}",
    "{:*<8}",
    "{name:>10}",
    "{name!r:>10}",
    "{0.attr}",
    "{0[1]}",
    "{items[0]}",
    "{items[key]}",
    "{partner.name!s:>4}",
)


@pytest.mark.parametrize("field", _FORMAT_FIELDS)
def test_format_fields_are_rejected_in_the_lenient_mode(field) -> None:
    assert find_unresolved_template_token(f"Hallo {field} und weiter.", strict_braces=False)
    assert find_unresolved_template_token(f"Hallo {field}", strict_braces=False)


@pytest.mark.parametrize("field", _FORMAT_FIELDS)
def test_format_fields_are_rejected_in_the_strict_mode(field) -> None:
    assert find_unresolved_template_token(f"Hallo {field} und weiter.", strict_braces=True)


@pytest.mark.parametrize(
    "text",
    (
        "Das Muster a{1,2} passt auf eine oder zwei Wiederholungen.",
        "Regex a{3} ist ein Quantor, kein Platzhalter.",
        "Die Formel x^{2} und \\frac{1}{2} stehen im Text.",
        "Die Menge { 3 } hat ein Element.",
        "Zahlen {1, 2, 3} im Beispiel.",
        "Menge {x: x>0} im Mengenaufbau.",
        "Leeres Objekt {} bleibt Text.",
        'JSON {"name": "Anna"} im Beispiel.',
        "Code: if (x) { return; } bleibt Prosa.",
        "Wert {1,5} und {a, b} ebenso.",
    ),
)
def test_quantifiers_math_and_code_braces_stay_prose_in_the_lenient_mode(text) -> None:
    assert find_unresolved_template_token(text, strict_braces=False) is None


# --------------------------------------------------------------------------- [a:foo]

_UNKNOWN_COMPACT_LABELS = (
    "Satz [a:foo] mit unbekannter ID.",
    "Satz [b:lifepath] falsch geschrieben.",
    "Satz [A:Nähe] gross.",
    "Satz [a:soul2] mit Ziffer.",
    "[a:attitudes] ist ein anderes Wort.",
)


@pytest.mark.parametrize("text", _UNKNOWN_COMPACT_LABELS)
def test_an_unknown_compact_label_is_rejected_in_the_strict_mode(text) -> None:
    """Analysen und Schatten-Dynamiken verbieten eckige Klammern im Prompt ausdruecklich;
    ein vollstaendig geschlossenes ``[a|b:bezeichner]`` ist dort ein Rest."""
    assert find_unresolved_template_token(text, strict_braces=True)


@pytest.mark.parametrize("text", _UNKNOWN_COMPACT_LABELS)
def test_an_unknown_compact_label_stays_prose_in_the_lenient_mode(text) -> None:
    """Report und Copilot: kein Beleg, dass die Form dort ein Token ist; ein unbekannter
    Bezeichner ohne Unterstrich bleibt Prosa (dokumentierte Entscheidung)."""
    assert find_unresolved_template_token(text, strict_braces=False) is None


@_BOTH_MODES
@pytest.mark.parametrize("text", ("Das Verhältnis [a:b] bleibt.", "Punkt [b:c], Punkt [x:yz]."))
def test_single_letter_ratio_and_other_person_letters_stay_prose(text, strict_braces) -> None:
    assert find_unresolved_template_token(text, strict_braces=strict_braces) is None


@_BOTH_MODES
def test_the_known_id_dialogue_case_is_a_documented_tradeoff(strict_braces) -> None:
    """``[a: Balance ...]`` als Dialogzeile beginnt mit einer bekannten Fakt-ID und wird
    wie das Label gelesen. Bewertung: das Modell schreibt das Label nie mit Blank nach dem
    Doppelpunkt; der Fall ist aber nach der Pruefansicht (casefold) nicht von
    ``[a:balance`` zu trennen, und ein false negative speichert ein internes Token als
    fertigen Text, ein false positive kostet einen Wiederholungsversuch. Bleibt streng."""
    assert find_unresolved_template_token(
        "[a: Balance ist mir wichtig.]", strict_braces=strict_braces
    )
    assert (
        find_unresolved_template_token("[a: Nähe ist mir wichtig.]", strict_braces=strict_braces)
        is None
    )


# --------------------------------------------------------------------------- Gegenproben

_INTERNATIONAL_PROSE = (
    "Größe, Maß, Straße, Übung, Ärger und Öl: schöne Grüße aus Köln, ÄÖÜ und äöü.",
    "Ayşe'nin ısı ölçümü: ışık, İstanbul, ILIK, ıspanak, İzmir ve ığdır.",
    "Καλημέρα κόσμε, ο Σωκράτης είπε: «γνῶθι σαυτόν». ΣΟΦΙΑ και φιλοσοφία.",
    "Привет, мир! Это обычный русский текст: «проверка». КОНТАКТ и Ѕвезда.",
    "日本語のテキスト：数字の三は「調和」を表します。[注] 参照。",
    "中文文本：数字三代表和谐，参见[1]和[注]。",
    "한국어 문장입니다. 숫자 3은 조화를 뜻합니다.",
    "Nähe \U0001f600 und Wärme \U0001f389 \U0001f468\u200d\U0001f469\u200d\U0001f467 "
    "mit Emoji [\U0001f642].",
    "\U0001f1e9\U0001f1ea Flagge, \u2764\ufe0f Herz und \u0031\ufe0f\u20e3 Keycap.",
    "مرحبا بالعالم، هذا نص عربي عادي [ملاحظة: نص] وأرقام ١٢٣ و ۴۵۶.",
    "שלום עולם, זהו טקסט עברי רגיל (עם סוגריים) ו־[הערה] עם נִקּוּד.",
    "Das Wort \u202bمرحبا\u202c steht im Satz, \u2067שלום\u2069 ebenfalls, \u200fRTL-Marke.",
    "Hindi: नमस्ते दुनिया [टिप्पणी] और संख्या ३. Thai: สวัสดีชาวโลก [หมายเหตu].",
    "Fullwidth: Ａｌｌｇｅｍｅｉｎ ｔｅｘｔ，ohne Token．",
    "Tilde ~ Backslash \\ Pipe | Caret ^ Hash # Dollar $ Prozent 50 % und 100%.",
    "Zitat: „Er sagte [sic], dass … [Anm.: ohne Quelle]“ – Ende.",
    "Treffen um [10:30] Uhr, Buch [1], Fussnote [12], Intervall [0, 1], Matrix [[1,2],[3,4]].",
    "Siehe [Text](https://example.org/a:b) und Aufgabe [x] erledigt, Aufgabe [ ] offen.",
    "Die ID metric:life_path und special:hidden_passion stehen in der Doku, nicht im Text.",
    "Teil a: Nähe und Teil b: Freiraum, a:b ist ein Verhältnis, [a] und [b] sind Varianten.",
    "Dialog: [A: Ich bin müde] [B: Das stimmt so nicht.] [a: Wärme bedeutet Ruhe].",
    "Er sagte [x:y] und [c:d] sowie [Abschnitt a: Nähe] und [Kapitel b: Freiraum].",
    "",
    " \n\t ",
)


@_BOTH_MODES
@pytest.mark.parametrize("text", _INTERNATIONAL_PROSE)
def test_international_prose_is_not_a_false_positive(text, strict_braces) -> None:
    assert find_unresolved_template_token(text, strict_braces=strict_braces) is None
    assert not contains_prompt_scaffolding(text)


@_BOTH_MODES
@pytest.mark.parametrize("text", _INTERNATIONAL_PROSE)
def test_the_check_never_changes_or_depends_on_the_stored_text(text, strict_braces) -> None:
    original = str(text)
    snapshot = list(original)
    find_unresolved_template_token(original, strict_braces=strict_braces)
    canonical_for_check(original)
    assert original == text
    assert list(original) == snapshot


def test_the_canonical_form_is_a_separate_view_that_does_differ() -> None:
    stored = "Größe \u0131 \u0130stanbul \u200b[Anm.]"
    assert canonical_for_check(stored) != stored
    assert stored == "Größe \u0131 \u0130stanbul \u200b[Anm.]"


# --------------------------------------------------------------------------- Laufzeit

_PERF_SHAPES = {
    "label-blanks-x": lambda n: "[a:" + " " * n + "x",
    "label-blanks": lambda n: "[a:" + " " * n,
    "blanks-label": lambda n: " " * n + "[a:",
    "repeated-label": lambda n: "[a:" * n,
    "repeated-compact": lambda n: "[a:x_" * n,
    "bracket-blanks": lambda n: "[" + " " * n,
    "repeated-bracket-blank": lambda n: "[ " * n,
    "known-id-blanks": lambda n: "[a:life_path" + " " * n + "x",
    "brace-blanks": lambda n: "{a" + " " * n + "x",
    "repeated-brace": lambda n: "{a:" * n,
    "brace-digits": lambda n: "{" + "0" * n,
    "brace-colon": lambda n: "{x" + ":" * n,
    "brace-bang": lambda n: "{" + "a" * n + "!",
    "brace-spec-blanks": lambda n: "{0:" + " " * n,
    "brace-spec-align": lambda n: "{0:" + ">" * n,
    "brace-index": lambda n: "{x" + "[" * n,
    "brace-index-body": lambda n: "{x[" + "a" * n,
    "brace-attr": lambda n: "{x" + ".a" * n,
    "repeated-open-brace": lambda n: "{" * n,
    "repeated-format-start": lambda n: "{0:" * n,
    "angle-word": lambda n: "<" + "a_" * n,
    "percent": lambda n: "%(" + "a" * n,
    "nfkd-bomb": lambda n: "\ufdfa" * n,
    "combining-flood": lambda n: "a" + "\u0301" * n,
    "invisible-flood": lambda n: "[" + "\u200b" * n + "a:",
}


@_BOTH_MODES
@pytest.mark.parametrize("shape", sorted(_PERF_SHAPES))
def test_pathological_inputs_up_to_the_cap_are_linear(shape, strict_braces) -> None:
    text = _PERF_SHAPES[shape](40_000)[:MAX_CHECKED_TEXT_CHARS]

    start = time.perf_counter()
    find_unresolved_template_token(text, strict_braces=strict_braces)

    assert time.perf_counter() - start < 2.0


@_BOTH_MODES
@pytest.mark.parametrize("shape", sorted(_PERF_SHAPES))
def test_the_scanner_itself_is_linear_beyond_the_cap(shape, strict_braces) -> None:
    """Der frueher quadratische Fall (``_short_label_alternatives`` mit Endanker) bleibt
    abgedeckt, auch wenn die Laengenobergrenze solche Eingaben vorher abfaengt: der
    Scanner wird hier ohne Grenze mit 300k+ Zeichen aufgerufen."""
    text = _PERF_SHAPES[shape](300_000)
    checked = canonical_for_check(text) if shape not in {"nfkd-bomb"} else text[:50_000]

    start = time.perf_counter()
    _find_in_canonical_form(checked, strict_braces=strict_braces)

    assert time.perf_counter() - start < 3.0


@_BOTH_MODES
def test_text_above_the_cap_is_rejected_fail_closed_without_processing(strict_braces) -> None:
    text = "Harmloser Satz. " * (MAX_CHECKED_TEXT_CHARS // 10)
    assert len(text) > MAX_CHECKED_TEXT_CHARS

    start = time.perf_counter()
    token = find_unresolved_template_token(text, strict_braces=strict_braces)

    assert token == OVERSIZE_TOKEN
    assert time.perf_counter() - start < 0.5


@_BOTH_MODES
def test_clean_text_exactly_at_the_cap_is_accepted(strict_braces) -> None:
    text = "a" * MAX_CHECKED_TEXT_CHARS
    assert find_unresolved_template_token(text, strict_braces=strict_braces) is None
    assert find_unresolved_template_token(text + "a", strict_braces=strict_braces) == OVERSIZE_TOKEN


def test_a_ten_million_character_input_is_rejected_immediately() -> None:
    start = time.perf_counter()
    assert find_unresolved_template_token("x" * 10_000_000) == OVERSIZE_TOKEN
    assert time.perf_counter() - start < 0.5


# --------------------------------------------------------------------------- Nutzlast


def test_payload_walker_finds_a_token_anywhere_in_nested_json() -> None:
    clean = {
        "a": [{"text": "Alles in Ordnung."}, ("noch ein Satz",)],
        "n": 3,
        "ok": True,
        "x": None,
    }
    assert find_unresolved_token_in_payload(clean) is None

    dirty = {"a": [{"text": "Alles in Ordnung."}, {"deep": ["x", ["y", "Rest [a:life_path]"]]}]}
    assert find_unresolved_token_in_payload(dirty) is not None
    assert find_unresolved_token_in_payload({"a": 1, "Titel {0}": "ok"}, strict_braces=False)


def test_payload_walker_honours_the_mode() -> None:
    payload = {"text": "Eine { einzelne Klammer"}
    assert find_unresolved_token_in_payload(payload, strict_braces=True) is not None
    assert find_unresolved_token_in_payload(payload, strict_braces=False) is None


def test_payload_walker_handles_deep_and_wide_payloads_without_recursion() -> None:
    deep: object = "Rest {{metric:x}}"
    for _ in range(5_000):
        deep = [deep]
    assert find_unresolved_token_in_payload(deep) is not None
    wide = {str(i): "sauberer Satz" for i in range(50_000)}
    assert find_unresolved_token_in_payload(wide) is None


# --------------------------------------------------------------------------- Property-Tests

_FLAGGED_FORMS = st.sampled_from(_TOKEN_FORMS)
_NOISE = st.lists(
    st.tuples(st.integers(min_value=0, max_value=1_000), st.sampled_from(_INVISIBLES)),
    max_size=8,
)
_PROSE_ALPHABET = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 \n\t.,;:!?-'\"/@#&*+=~^_|"
    "äöüßÄÖÜéèçñıİ"
    "абвгдежзийклмнопрстуфхцчшщыэюя"
    "αβγδεζηθικλμνξοπρστυφχψω"
    "日本語中文한국어😀"
)


@settings(max_examples=300, deadline=None)
@given(form=_FLAGGED_FORMS, noise=_NOISE, strict=st.booleans())
def test_property_invisible_noise_never_hides_a_token(form, noise, strict) -> None:
    forged = form
    for raw_position, invisible in noise:
        position = raw_position % (len(forged) + 1)
        forged = forged[:position] + invisible + forged[position:]
    assert find_unresolved_template_token(f"Satz {forged} Ende.", strict_braces=strict)


@settings(max_examples=300, deadline=None)
@given(text=st.text(alphabet=_PROSE_ALPHABET, max_size=400), strict=st.booleans())
def test_property_text_without_bracket_characters_is_never_flagged(text, strict) -> None:
    assert find_unresolved_template_token(text, strict_braces=strict) is None


@settings(max_examples=300, deadline=None)
@given(text=st.text(max_size=400), strict=st.booleans())
def test_property_the_detector_is_total_and_returns_only_a_short_token(text, strict) -> None:
    token = find_unresolved_template_token(text, strict_braces=strict)
    assert token is None or 0 < len(token) <= 64
