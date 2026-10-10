"""Tests fuer content_checks: PDF-Inhaltspruefung mit Negativ-Gegenprobe."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import content_checks as cc  # noqa: E402
from pdf_fixtures import GERMAN, make_pdf  # noqa: E402


def verdicts(data: bytes, **kwargs):
    return {i: (ok, ev) for i, _, ok, ev in cc.evaluate_pdf(cc.analyze_pdf(data), **kwargs)}


def test_good_german_pdf_passes_all_checks():
    result = verdicts(make_pdf([GERMAN, GERMAN]))
    assert all(ok for ok, _ in result.values()), result
    assert result["9"][1] == "pages=2"


def test_text_is_really_extracted_not_guessed():
    analysis = cc.analyze_pdf(make_pdf([GERMAN]))
    assert "Bericht" in analysis.text and "Stärken" in analysis.text
    assert analysis.pages == 1 and analysis.words > 80


@pytest.mark.parametrize(
    "bad_line",
    ["Hallo [a: profile_fact] Welt", "Hallo {{name}} Welt", "Hallo {vorname} Welt"],
)
def test_placeholder_negative_control(bad_line):
    result = verdicts(make_pdf([GERMAN + [bad_line]]))
    assert result["10c"][0] is False
    assert result["10a"][0] and result["10b"][0]


def test_clean_pdf_has_zero_hits():
    assert cc.analyze_pdf(make_pdf([GERMAN])).hits == []


def test_english_text_fails_language_check():
    english = [
        "Your personal report shows how you deal with change and what gives you the strength",
        "to continue. The numbers are not a fixed forecast but an invitation to notice your own",
        "patterns. If you are feeling overwhelmed it is often helpful to plan small steps and",
        "to take breaks seriously. Even in difficult weeks you can focus on what already works",
        "and this is the result that will become clearer with your development over time so that",
        "you can make new decisions with more calm and with a good feeling for your strengths",
    ]
    result = verdicts(make_pdf([english * 2]), min_words=20)
    assert result["10b"][0] is False


def test_too_few_words_and_page_bounds():
    short = make_pdf([["Kurz."]])
    assert verdicts(short)["10a"][0] is False
    assert verdicts(make_pdf([GERMAN] * 3), max_pages=2)["9"][0] is False
    assert verdicts(make_pdf([GERMAN]), min_pages=2)["9"][0] is False


@pytest.mark.parametrize("garbage", [b"", b"%PDF-1.4 kaputt", b"kein pdf"])
def test_unreadable_pdf_fails_instead_of_skipping(garbage):
    result = cc.evaluate_pdf(cc.analyze_pdf(garbage))
    assert len(result) == 1 and result[0][2] is False and "Lesefehler" in result[0][3]


def test_text_quality_json_detects_placeholder():
    clean = {"a": ["Das ist ein ganz normaler deutscher Satz mit genug Woertern."]}
    dirty = {"a": ["Das ist ein ganz normaler Satz mit {{token}} und genug Woertern."]}
    assert cc.text_quality(clean)["hits"] == []
    assert cc.text_quality(dirty)["hits"]


def test_encrypted_pdf_fails_with_specific_text():
    import io

    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for page in PdfReader(io.BytesIO(make_pdf([GERMAN]))).pages:
        writer.add_page(page)
    writer.encrypt("geheim")
    buffer = io.BytesIO()
    writer.write(buffer)
    result = cc.evaluate_pdf(cc.analyze_pdf(buffer.getvalue()))
    assert len(result) == 1 and result[0][2] is False and "verschluesselt" in result[0][3]


def test_image_only_pdf_fails_text_check_with_hint():
    result = {i: (ok, ev) for i, _, ok, ev in cc.evaluate_pdf(cc.analyze_pdf(make_pdf([[]])))}
    assert result["10a"][0] is False and "Bild-PDF" in result["10a"][1]


def test_min_pdf_bytes_is_one_constant():
    assert cc.MIN_PDF_BYTES == 20480
