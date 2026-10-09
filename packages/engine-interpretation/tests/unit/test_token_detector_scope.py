"""Regression: Reichweite des Token-Detektors -- eng genug fuer Fliesstext, streng genug fuer
Reste (Review zu PR #308).

* Das verkuerzte Label wird nur mit *bekannter* Metrik-ID erkannt (oder abgeschnitten am
  Textende), damit Dialogzitate in Klammern Prosa bleiben.
* Report und Copilot lehnen nur konkrete Platzhalterformen ab, nicht jede einzelne
  Klammer; die Analyse-/Schatten-Pipeline behaelt das strenge Verhalten.
"""

from __future__ import annotations

import datetime as dt
import time

import pytest

from numra_interpretation.llm.rendering_guard import find_unresolved_template_token
from numra_interpretation.llm.validator import (
    KNOWN_FACT_IDS,
    build_metric_display_value_index,
    build_special_claim_index,
)
from numra_numerology.engine import calculate_profile
from numra_numerology.models.person import PersonInput

pytestmark = pytest.mark.unit


def test_known_fact_ids_equal_the_profile_indices() -> None:
    profile = calculate_profile(
        PersonInput(
            birth_first_names="Anna",
            birth_middle_names="Marie",
            birth_last_name="Berger",
            birth_date=dt.date(1990, 3, 14),
        ),
        as_of_date=dt.date(2026, 8, 19),
    )

    index_ids = set(build_metric_display_value_index(profile)) | set(
        build_special_claim_index(profile)
    )

    assert index_ids == KNOWN_FACT_IDS


# ------------------------------------------------------------------ Kurzform: beide Richtungen

_REJECTED_SHORT_FORMS = (
    "Satz [a:life_path] im Satz.",
    "Satz [a: life_path] mit Blank.",
    "Satz [ A : expression ] mit Gross und Blanks.",
    "Satz [B:SOUL_URGE] gross.",
    "Satz [b:soul_urge",  # Textende, ID vollstaendig
    "Satz [b:soul_u",  # Textende, ID abgeschnitten
    "Satz [a:",  # Textende direkt nach dem Doppelpunkt
    "Satz [a: ",  # Textende nach Blank
    "Satz [a:life_path_extra] bekannte ID mit Anhang.",
    "Satz [a:does_not_exist] unbekannt, aber Label-Form.",
    "Satz [a:hidden_passion] Special-ID.",
    "Satz [a:challenge_4] hoechste Challenge-ID.",
    "Satz [a:life_path und geht weiter.",
    "Satz [a:life_path, danach mehr.",
    "Satz [a:life_path. Danach mehr.",
    "Satz [b:expression) mit Klammer.",
    "Satz [a: soul_urge und mehr.",
    "Satz [а:life_path] kyrillisches a.",
    "Satz [A​:life_path] Zero-Width.",
    "Satz ［Ａ：ｌife_path］ voll breit.",
    "Satz [á:expression] Combining Mark.",
)


@pytest.mark.parametrize("text", _REJECTED_SHORT_FORMS)
def test_label_shaped_text_is_rejected(text) -> None:
    assert find_unresolved_template_token(text) is not None


_ACCEPTED_BRACKET_TEXT = (
    "[A: Ich bin müde]",
    "Er sagte leise [a: Nähe] und ging.",
    "[B: Das stimmt so nicht.] [A: Doch.]",
    "Dialog: [a: Wärme bedeutet für mich Ruhe] und weiter.",
    "Satz [a:attitudes] ist ein anderes Wort.",
    "Satz [a:foo] bleibt Prosa wie entschieden.",
    "[a: balanced und ruhig]",
    "Siehe [Text](https://example.org/a:b) im Anhang.",
    "Aufgabe [x] erledigt, Aufgabe [ ] offen.",
    "Sie sagte: „Ich komme [b: später]“ und lachte.",
    "Treffen um [10:30] Uhr, Buch [1].",
    "Teil [a] und Teil [b].",
    "[a:b]",
    "Das Verhältnis a:b bleibt im Fliesstext.",
    "[Abschnitt a: Nähe]",
)


@pytest.mark.parametrize("text", _ACCEPTED_BRACKET_TEXT)
@pytest.mark.parametrize("strict_braces", [True, False])
def test_dialogue_links_and_checkboxes_stay_prose(text, strict_braces) -> None:
    assert find_unresolved_template_token(text, strict_braces=strict_braces) is None


# ------------------------------------------------------------------ Klammern: streng vs. locker

_PLACEHOLDER_REMNANTS = (
    "Die Reifezahl {{metric:maturity}} verbindet.",
    "Die Reifezahl {{metric:maturit",
    "Die Reifezahl {{ metric : a : life_path }} verbindet.",
    "maturity}} verbindet Lebensweg und Ausdruck.",
    "Die Reifezahl {metric:maturity} mit einfachen Klammern.",
    "Die Reifezahl {metric:matur",
    "Hallo {partner_a} und {partner.name}.",
    "Hallo {metric.life_path}.",
    "Hallo <partner_a> und %(partner_b)s.",
    "Die Zahl [metric:life_path] mit falschen Klammern.",
)


@pytest.mark.parametrize("text", _PLACEHOLDER_REMNANTS)
@pytest.mark.parametrize("strict_braces", [True, False])
def test_placeholder_remnants_are_rejected_in_both_modes(text, strict_braces) -> None:
    assert find_unresolved_template_token(text, strict_braces=strict_braces) is not None


_ISOLATED_BRACES = (
    "Das Muster a{1,2} passt auf eine oder zwei Wiederholungen.",
    "Die Menge { 3 } hat ein Element.",
    "Eine einzelne { Klammer bleibt moeglich.",
    "Und eine schliessende } ebenfalls.",
    "Zahlen {1, 2, 3} im Beispiel.",
)


@pytest.mark.parametrize("text", _ISOLATED_BRACES)
def test_isolated_braces_are_prose_for_report_and_copilot(text) -> None:
    assert find_unresolved_template_token(text, strict_braces=False) is None


@pytest.mark.parametrize("text", _ISOLATED_BRACES)
def test_isolated_braces_stay_rejected_for_analyses(text) -> None:
    assert find_unresolved_template_token(text) is not None


# ------------------------------------------------------------------ Laufzeit (ReDoS)

_PERF_SIZES = (20_000, 200_000)
_PERF_INPUTS = {
    "label-blanks-x": lambda n: "[a:" + " " * n + "x",
    "label-blanks": lambda n: "[a:" + " " * n,
    "blanks-label": lambda n: " " * n + "[a:",
    "repeated-label": lambda n: "[a:" * n,
    "bracket-blanks": lambda n: "[" + " " * n,
    "bracket-blanks-bracket": lambda n: "[" + " " * n + "[a:",
    "repeated-bracket-blank": lambda n: "[ " * n,
    "known-id-blanks": lambda n: "[a:life_path" + " " * n + "x",
    "brace-blanks": lambda n: "{a" + " " * n + "x",
    "repeated-brace": lambda n: "{a:" * n,
    "angle-word": lambda n: "<" + "a_" * n,
    "percent": lambda n: "%(" + "a" * n,
}


@pytest.mark.parametrize("size", _PERF_SIZES)
@pytest.mark.parametrize("shape", sorted(_PERF_INPUTS))
@pytest.mark.parametrize("strict_braces", [True, False])
def test_worst_case_inputs_are_checked_in_linear_time(shape, size, strict_braces) -> None:
    text = _PERF_INPUTS[shape](size)

    start = time.perf_counter()
    find_unresolved_template_token(text, strict_braces=strict_braces)

    assert time.perf_counter() - start < 1.0


@pytest.mark.parametrize("text", ["Satz [a:", "Satz [b:soul_u", "Satz [a: ", "Satz [a:life_path"])
def test_a_label_cut_off_at_the_end_is_still_rejected(text) -> None:
    assert find_unresolved_template_token(text) is not None


@pytest.mark.parametrize("text", ["Satz [a:   x", "Satz [a: Ich bin mü", "Satz [a:zzz"])
def test_a_bracket_at_the_end_that_is_no_label_prefix_is_prose(text) -> None:
    assert find_unresolved_template_token(text) is None
