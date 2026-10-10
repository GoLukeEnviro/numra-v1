"""Regression: `find_unresolved_template_token` -- the one check every LLM pipeline runs
over a text that is about to become a result.

Anlass (Audit-Abnahme 2026-10-09): neu erzeugte Beziehungsanalysen enthielten das
verkuerzte Block-Label ``[a:life_path]`` / ``[b:expression]`` (Rolle, Doppelpunkt,
Metrik-ID -- ohne das Praefix ``profile_fact:``) und ein Report in der Zusammenfassung ein
``{{metric:maturity}}``. Beides wurde als COMPLETE gespeichert, weil kein Detektor die Form
kannte. Die Beispielsaetze unten sind neu formuliert; nur die Token-Formen sind echt.
"""

from __future__ import annotations

import time

import pytest

from numra_interpretation.llm.rendering_guard import (
    MAX_CHECKED_TEXT_CHARS,
    OVERSIZE_TOKEN,
    PROMPT_SCAFFOLDING_MARKERS,
    canonical_for_check,
    contains_prompt_scaffolding,
    find_unresolved_template_token,
)

pytestmark = pytest.mark.unit

#: Die Metrik-IDs, die im Audit als verkuerztes Label auftraten (Rolle a/b).
_AUDIT_METRIC_IDS = (
    "life_path",
    "expression",
    "soul_urge",
    "attitude",
    "balance",
    "subconscious_self",
    "personal_year",
    "challenge_1",
    "challenge_2",
)

_AUDIT_SENTENCES = (
    "Im Gespräch bringt Person A durch [a:life_path] eine offene Perspektive ein.",
    "Im Austausch wirkt [a:expression] offen, während [b:expression] eine ruhigere Linie hält.",
    "Die Nähe zeigt sich zwischen [a:life_path] und [b:life_path] im Alltag.",
    "Bedürfnisse: [b:soul_urge] sucht Tiefe, [a:soul_urge] eher Weite.",
    "Haltung [a:attitude], Balance [b:balance], Unterbewusstsein [a:subconscious_self].",
    "Persönliches Jahr [a:personal_year], Herausforderung [b:challenge_2] und [a:challenge_1].",
)


@pytest.mark.parametrize("sentence", _AUDIT_SENTENCES)
def test_audit_sentences_with_the_shortened_label_are_flagged(sentence) -> None:
    assert find_unresolved_template_token(sentence) is not None


@pytest.mark.parametrize("role", ["a", "b"])
@pytest.mark.parametrize("metric_id", _AUDIT_METRIC_IDS)
def test_every_audit_form_is_flagged(role, metric_id) -> None:
    assert find_unresolved_template_token(f"Ein Satz mit [{role}:{metric_id}] mittendrin.")


@pytest.mark.parametrize(
    "text",
    (
        "Satz [A:life_path] gross.",
        "Satz [a: life_path] mit Blank.",
        "Satz [ a : life_path ] mit vielen Blanks.",
        "Satz [a:LIFE_PATH] gross.",
        "Satz [b:Soul_Urge] gemischt.",
        "Satz [a:unbekannte_metrik] unbekannte ID.",
        "Satz [a:life_pa",  # Antwort mitten im Token abgeschnitten
        "Satz [b:soul_urge",  # ohne schliessende Klammer
        "Satz endet mit [a:",  # abgeschnitten direkt nach dem Doppelpunkt
        "Satz [a:[a:life_path]] verschachtelt.",
        "Satz [[a:life_path]] doppelt geklammert.",
    ),
)
def test_variants_and_truncated_forms_are_flagged(text) -> None:
    assert find_unresolved_template_token(text) is not None


@pytest.mark.parametrize(
    "text",
    (
        "Die Reifezahl {{metric:maturity}} verbindet Lebensweg und Ausdruck.",  # wohlgeformt
        "Die Reifezahl {{metric:maturit",  # abgeschnitten, nie geschlossen
        "…maturity}} verbindet Lebensweg und Ausdruck.",  # nur der Schluss
        "Die Reifezahl {{metric:matur…",
        "Die Zahl {{ metric : a : life_path }} im Satz.",
        "Die Zahl {{special:hidden_passion}} im Satz.",
        "Die Zahl {metric:life_path} mit einfachen Klammern.",
        "Die Zahl [metric:a:life_path] mit falschen Klammern.",
        "Die Zahl <special:b:hidden_passion> mit Spitzklammern.",
        "Hallo {partner_a} und %(partner_b)s und <partner_a>.",
    ),
)
def test_placeholder_remnants_are_flagged(text) -> None:
    assert find_unresolved_template_token(text) is not None


@pytest.mark.parametrize(
    "text",
    (
        "Satz [а:life_path] mit kyrillischem a.",
        "Satz [А:life_path] mit grossem kyrillischem A.",
        "Satz ［ａ：life_path］ voll breit.",
        "Satz [a​:life_path] mit Zero-Width.",
        "Satz [á:life_path] mit Combining Mark.",
        "Satz [a:life​_path] mit Zero-Width in der ID.",
        "Satz ｛｛metric:maturity｝｝ voll breit.",
    ),
)
def test_lookalike_forms_use_the_same_check_form(text) -> None:
    assert find_unresolved_template_token(text) is not None


@pytest.mark.parametrize("marker", PROMPT_SCAFFOLDING_MARKERS)
def test_scaffolding_markers_stay_flagged_and_the_guard_is_unchanged(marker) -> None:
    text = f"Satz mit {marker} mittendrin."
    assert contains_prompt_scaffolding(text)
    assert find_unresolved_template_token(text) == marker


@pytest.mark.parametrize(
    "text",
    (
        "Treffen um [10:30] Uhr, danach Pause.",
        "Siehe Buch [1] und Fussnote [12].",
        "Ein Verhältnis a:b von zwei zu drei, im Fliesstext.",
        "Teil a: und Teil b: werden getrennt betrachtet.",
        "Aufzählung: a) Nähe, b) Freiraum, c) Vertrauen.",
        "Variante [a] oder Variante [b] stehen zur Wahl.",
        "Das Zitat „… [sic] …“ bleibt unverändert.",
        "Anmerkung [Anmerkung: ohne Rolle] und [Abschnitt a: Nähe] sind Prosa.",
        "Klammern (wie hier) und [Anmerkung der Redaktion] sind normale Prosa.",
        "Über Grenzen hinweg: „Nähe“ und »Freiraum« – größer, schöner, behutsamer. 25/7 … 100 %.",
        "Он сказал «да» (русский текст), und α, β, γ bleiben erlaubt.",
        "Gespräch mit José, Zoë und Renée: „Café“ und Naïve Künstler – fertig.",
        "Ѕtraße und КОНТАКТ: Großbuchstaben bleiben Prosa, ebenso ΣΟΦΙΑ und İstanbul.",
        "",
    ),
)
def test_ordinary_german_prose_is_not_a_false_positive(text) -> None:
    assert find_unresolved_template_token(text) is None


def test_the_returned_token_is_short_and_never_carries_surrounding_prose() -> None:
    token = find_unresolved_template_token("Geheimer Satz Anna Berger [a:life_path] geht weiter.")
    assert token is not None
    assert len(token) <= 24
    assert "Anna" not in token and "Satz" not in token


def test_check_is_linear_in_the_input_length() -> None:
    sample = "Über José: [Anmerkung] Ѕystem prófile straße a:b. " * 570
    assert 25_000 < len(sample) <= MAX_CHECKED_TEXT_CHARS
    start = time.perf_counter()
    assert find_unresolved_template_token(sample) is None
    assert time.perf_counter() - start < 5.0


def test_text_beyond_the_length_limit_is_rejected_not_scanned() -> None:
    sample = "Über José: [Anmerkung] Ѕystem prófile straße a:b. " * 22_000
    assert len(sample) > MAX_CHECKED_TEXT_CHARS
    assert find_unresolved_template_token(sample) == OVERSIZE_TOKEN


def test_canonical_form_folds_case_width_and_invisible_characters() -> None:
    assert canonical_for_check("［A​：life_path］") == "[a:life_path]"
