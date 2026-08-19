from __future__ import annotations

import pytest

from numra_numerology.models.errors import NormalizationUnsupportedScript
from numra_numerology.normalization.pipeline import normalize_name

pytestmark = pytest.mark.unit


def test_basic_two_component_name() -> None:
    result = normalize_name("Lukas Springer")
    assert result.components == ("LUKAS", "SPRINGER")
    assert result.calculation_string == "LUKASSPRINGER"


def test_german_umlaut_replacement_not_ae_expansion() -> None:
    result = normalize_name("Jürgen Müller")
    assert result.calculation_string == "JURGENMULLER"


def test_sharp_s_becomes_ss() -> None:
    result = normalize_name("Straße")
    assert result.calculation_string == "STRASSE"


def test_capital_sharp_s_becomes_ss() -> None:
    result = normalize_name("STRAẞE")
    assert result.calculation_string == "STRASSE"


def test_hyphenated_name_multiple_components() -> None:
    result = normalize_name("Anna-Maria von Beispiel")
    assert result.components == ("ANNA", "MARIA", "VON", "BEISPIEL")


def test_apostrophe_name_splits_components() -> None:
    result = normalize_name("O'Brien")
    assert result.components == ("O", "BRIEN")


def test_various_latin_diacritics() -> None:
    result = normalize_name("Ñoño Çedric Éowyn Àbel")
    assert result.calculation_string == "NONOCEDRICEOWYNABEL"


def test_unsupported_script_raises() -> None:
    with pytest.raises(NormalizationUnsupportedScript):
        normalize_name("Иван")


def test_unsupported_script_cjk_raises() -> None:
    with pytest.raises(NormalizationUnsupportedScript):
        normalize_name("田中")


def test_digits_raise_unsupported_script() -> None:
    with pytest.raises(NormalizationUnsupportedScript):
        normalize_name("Anna2")


def test_empty_components_discarded() -> None:
    result = normalize_name("  Anna   Maria  ")
    assert result.components == ("ANNA", "MARIA")


def test_period_punctuation_stripped() -> None:
    result = normalize_name("St. Martin")
    assert result.components == ("ST", "MARTIN")
