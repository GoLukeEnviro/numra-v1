"""Regression: ein Report darf keinen ungeloesten Template-Token als fertiges Ergebnis
ausgeben -- weder im Abschnittstext noch in der Zusammenfassung.

Anlass (Audit-Abnahme 2026-10-09): in drei als COMPLETE gespeicherten Reports (QUICK, FULL,
ULTIMATE) stand im ``summary``-Feld des Abschnitts ``maturity`` ein ``{{metric:maturity}}``.
Ursache: die Pipeline loeste Platzhalter nur im ``text`` auf; die ``summary`` des Providers
wurde unveraendert uebernommen, und der globale Linter prueft nur ``section.text``. Die
Metrik-ID war gueltig -- das Modell hat den Platzhalter korrekt, aber im falschen Feld
geschrieben.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from numra_interpretation.knowledge_loader import load_knowledge_base
from numra_interpretation.llm.types import (
    GenerationRequest,
    GenerationResult,
    ProviderHealth,
    StructuredGenerationRequest,
)
from numra_interpretation.llm.validator import build_metric_display_value_index
from numra_interpretation.report import build_manifest, generate_report, lint_report
from numra_interpretation.report.pipeline import ReportGenerationError
from numra_interpretation.report.schemas import GeneratedSectionContent, StructuredReportSection
from numra_numerology.engine import calculate_profile
from numra_numerology.models.person import PersonInput

pytestmark = pytest.mark.unit

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[4] / "knowledge"


@pytest.fixture(scope="module")
def knowledge_base():
    return load_knowledge_base(KNOWLEDGE_ROOT)


@pytest.fixture(scope="module")
def profile():
    return calculate_profile(
        PersonInput(
            birth_first_names="Anna",
            birth_middle_names="Marie",
            birth_last_name="Berger",
            birth_date=dt.date(1990, 3, 14),
        ),
        as_of_date=dt.date(2026, 8, 19),
    )


def _filler(section_id: str, target_word_count: int) -> str:
    words = (f"platzhaltertext für {section_id}".split() * (target_word_count // 3 + 1))[
        :target_word_count
    ]
    return " ".join(words)


class _Provider:
    """Ein echter (nicht-mock) Provider: ``summary_for``/``text_for`` bekommen
    ``(section_id, attempt)`` und liefern das Feld; fehlt ``text_for``, ist der Text sauberer
    Fuelltext in Zielluenge."""

    def __init__(self, *, summary_for=None, text_for=None) -> None:
        self.summary_for = summary_for or (lambda _sid, _attempt: "Kurzfassung.")
        self.text_for = text_for

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            status="healthy", provider="ollama_cloud", checked_at=dt.datetime.now(dt.UTC)
        )

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        raise AssertionError("not used")

    async def generate_structured(self, request: StructuredGenerationRequest, schema: type):  # type: ignore[no-untyped-def]
        if schema is not GeneratedSectionContent:
            return schema()
        section_id = request.metadata["section_id"]
        attempt = request.metadata["attempt"]
        filler = _filler(section_id, int(request.metadata["target_word_count"]))
        text = self.text_for(section_id, attempt, filler) if self.text_for else filler
        return schema(
            title=section_id,
            text=text,
            numeric_claims=request.numeric_claims,
            summary=self.summary_for(section_id, attempt),
        )


async def _generate(profile, knowledge_base, provider):
    manifest = build_manifest(report_type="QUICK", calculation_id="calc-1")
    return await generate_report(
        profile=profile, knowledge=knowledge_base, manifest=manifest, llm=provider
    )


# ------------------------------------------------------------------ Aufloesung der summary


@pytest.mark.parametrize("metric_id", ["maturity", "life_path"])
async def test_a_placeholder_in_the_summary_is_resolved_to_the_canonical_value(
    metric_id, profile, knowledge_base
) -> None:
    canonical = build_metric_display_value_index(profile)[metric_id]
    provider = _Provider(
        summary_for=lambda _sid, _a: f"Die Zahl {{{{metric:{metric_id}}}}} verbindet den Weg."
    )

    report = await _generate(profile, knowledge_base, provider)

    assert report.sections
    for section in report.sections:
        assert section.summary == f"Die Zahl {canonical} verbindet den Weg."
        assert "{" not in section.summary and "}" not in section.summary


async def test_a_summary_placeholder_is_resolved_on_the_repair_attempt_too(
    profile, knowledge_base
) -> None:
    provider = _Provider(
        summary_for=lambda _sid, attempt: (
            "Die Zahl {{metric:maturit" if attempt == "1" else "Saubere Kurzfassung."
        )
    )

    report = await _generate(profile, knowledge_base, provider)

    assert all(s.summary == "Saubere Kurzfassung." for s in report.sections)


# ------------------------------------------------------------------ Ablehnung (Pipeline)


@pytest.mark.parametrize(
    "bad_summary",
    (
        "Die Reifezahl {{metric:maturit",  # Antwort mitten im Platzhalter abgeschnitten
        "Die Reifezahl {{metric:maturity",  # schliessende Klammern fehlen
        "maturity}} verbindet Lebensweg und Ausdruck.",  # nur der Schluss
        "Die Reifezahl {{metric:does_not_exist}} verbindet.",  # unbekannte ID
        "Die Reifezahl {{special:does_not_exist}} verbindet.",
        "Die Reifezahl [metric:maturity] verbindet.",  # falsche Klammern
        "Die Reifezahl [a:maturity] verbindet.",  # verkuerztes Label
        "Die Reifezahl [profile_fact:maturity] verbindet.",  # Prompt-Geruest
    ),
)
async def test_a_bad_summary_never_makes_a_report(bad_summary, profile, knowledge_base) -> None:
    provider = _Provider(summary_for=lambda _sid, _a: bad_summary)

    with pytest.raises(ReportGenerationError, match="REPORT_SECTION_UNRENDERABLE"):
        await _generate(profile, knowledge_base, provider)


@pytest.mark.parametrize(
    "bad_text",
    (
        "Die Reifezahl {{metric:maturit",
        "Die Reifezahl {{metric:maturity",
        "maturity}} verbindet Lebensweg und Ausdruck.",
        "Die Reifezahl [metric:maturity] verbindet.",
        "Die Reifezahl [a:maturity] verbindet.",
        "Die Reifezahl {maturity} verbindet.",
    ),
)
async def test_a_text_with_a_token_remnant_never_makes_a_report(
    bad_text, profile, knowledge_base
) -> None:
    provider = _Provider(text_for=lambda _sid, _a, filler: f"{bad_text} {filler}")

    with pytest.raises(ReportGenerationError, match="REPORT_SECTION_UNRENDERABLE"):
        await _generate(profile, knowledge_base, provider)


async def test_the_error_names_the_token_but_no_provider_prose(profile, knowledge_base) -> None:
    provider = _Provider(summary_for=lambda _sid, _a: "Vertraulicher Satz {{metric:matur")

    with pytest.raises(ReportGenerationError) as excinfo:
        await _generate(profile, knowledge_base, provider)

    assert "summary" in str(excinfo.value)
    assert "Vertraulicher" not in str(excinfo.value)


# ------------------------------------------------------------------ Backstop (Linter)


def _sections(manifest, **overrides):
    return tuple(
        StructuredReportSection(
            section_id=spec.section_id,
            title=overrides.get("title", spec.title),
            order_index=spec.order_index,
            text=overrides.get("text", f"{spec.section_id} " * 50),
            word_count=50,
            summary=overrides.get("summary", "Kurzfassung."),
        )
        for spec in manifest.sections
    )


@pytest.mark.parametrize("field", ["text", "summary", "title"])
@pytest.mark.parametrize(
    "remnant",
    (
        "{{metric:maturity}}",
        "{{metric:matur",
        "maturity}}",
        "[a:life_path]",
        "[profile_fact:life_path]",
    ),
)
def test_lint_report_flags_a_token_remnant_in_every_field(field, remnant, profile) -> None:
    manifest = build_manifest(
        report_type="CUSTOM", calculation_id="calc-1", custom_total_target_words=100
    )
    sections = _sections(manifest, **{field: f"Satz {remnant} Ende. " * 3})

    result = lint_report(manifest, sections, profile)

    assert not result.is_valid
    assert any("PlaceholderResolution" in error and field in error for error in result.errors)


def test_lint_report_accepts_clean_fields(profile) -> None:
    manifest = build_manifest(
        report_type="CUSTOM", calculation_id="calc-1", custom_total_target_words=100
    )

    result = lint_report(manifest, _sections(manifest), profile)

    assert not any("PlaceholderResolution" in error for error in result.errors)


# ------------------------------------------------------------------ einzelne Klammern


@pytest.mark.parametrize(
    "brace_text",
    (
        "Das Muster a{1,2} passt auf ein bis zwei Wiederholungen.",
        "Die Menge { 3 } hat ein Element.",
        "Eine einzelne { Klammer bleibt Prosa.",
        "Und eine schliessende } ebenfalls.",
    ),
)
@pytest.mark.parametrize("field", ["text", "summary"])
async def test_an_isolated_brace_does_not_fail_a_report(
    field, brace_text, profile, knowledge_base
) -> None:
    if field == "text":
        provider = _Provider(text_for=lambda _sid, _a, filler: f"{brace_text} {filler}")
    else:
        provider = _Provider(summary_for=lambda _sid, _a: brace_text)

    report = await _generate(profile, knowledge_base, provider)

    assert report.sections


@pytest.mark.parametrize("field", ["text", "summary", "title"])
def test_lint_report_accepts_an_isolated_brace_but_not_a_placeholder_shape(field, profile) -> None:
    manifest = build_manifest(
        report_type="CUSTOM", calculation_id="calc-1", custom_total_target_words=100
    )

    ok = lint_report(
        manifest, _sections(manifest, **{field: "Muster a{1,2} und eine } offen."}), profile
    )
    bad = lint_report(
        manifest, _sections(manifest, **{field: "Rest {partner_a} im Satz."}), profile
    )

    assert not any("PlaceholderResolution" in error for error in ok.errors)
    assert any("PlaceholderResolution" in error for error in bad.errors)
