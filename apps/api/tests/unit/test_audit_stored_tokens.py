"""Betriebsskript ``scripts/ops/audit_stored_tokens.py``: zaehlt Treffer-Kategorien und
gibt nie einen Text aus."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).parents[4] / "scripts" / "ops" / "audit_stored_tokens.py"
_SPEC = importlib.util.spec_from_file_location("audit_stored_tokens", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
audit_stored_tokens = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(audit_stored_tokens)

pytestmark = pytest.mark.unit


def _line(kind: str, payload: object, bucket: str = "v1") -> str:
    return json.dumps({"kind": kind, "bucket": bucket, "payload": payload})


def test_counts_documents_hits_and_categories_per_kind() -> None:
    result = audit_stored_tokens.audit(
        [
            _line("report_section", {"text": "Sauberer Satz.", "summary": "Kurz."}),
            _line("report_section", {"text": "Rest {{metric:maturity}} im Satz."}),
            _line("report_section", {"text": "Format {0} im Satz."}),
            _line("report_section", {"text": "Label [a:life_path] im Satz."}),
            _line("relationship", {"dimensions": [{"statements": [{"text": "Rest [a:foo]"}]}]}),
            _line("chat", "Eine { einzelne Klammer ist im Chat Prosa."),
            _line("shadow", "Eine { einzelne Klammer ist in der Analyse ein Rest."),
        ]
    )

    kinds = result["kinds"]
    section = kinds["report_section"]
    assert section["documents"] == 4 and section["documents_with_hit"] == 3
    assert section["hit_categories"] == {"brace_field": 1, "placeholder": 1, "short_label": 1}
    assert kinds["relationship"]["hit_categories"] == {"short_label": 1}
    assert kinds["chat"]["documents_with_hit"] == 0 and kinds["chat"]["mode"] == "lenient"
    assert kinds["shadow"]["hit_categories"] == {"single_brace": 1}
    assert kinds["shadow"]["mode"] == "strict"
    assert result["detector"] == "hardened"


def test_legacy_matches_that_the_detector_leaves_as_prose_are_counted_by_shape_only() -> None:
    result = audit_stored_tokens.audit(
        [
            _line("report_section", "Ein Verhaeltnis [a:foo] und [x:y_z] im Text."),
            _line("report_section", "Reihe [b:ab] ohne Beleg."),
        ]
    )

    section = result["kinds"]["report_section"]
    assert section["documents_with_hit"] == 0
    assert section["legacy_regex_documents"] == 2
    assert section["legacy_regex_documents_detector_clean"] == 2
    assert section["legacy_clean_shapes"] == {
        "bracket_ab_plain_word": 2,
        "bracket_other_letter_snake_case": 1,
    }


def test_output_never_contains_a_text_an_id_or_a_bucket_value_of_the_input() -> None:
    secret = "Vertraulich Anna Berger"
    result = audit_stored_tokens.audit(
        [_line("chat", f"{secret} {{0}} und [a:geheim_id]", bucket="prompt-secret-v9")]
    )
    rendered = json.dumps(result)

    assert "Vertraulich" not in rendered and "Anna" not in rendered
    assert "geheim_id" not in rendered
    assert result["kinds"]["chat"]["documents_with_hit"] == 1


def test_invalid_lines_are_counted_not_raised_and_blank_lines_skipped() -> None:
    result = audit_stored_tokens.audit(["", "kein json", json.dumps({"kind": "chat"}), "[1]"])

    assert result["invalid_lines"] == 3
    assert result["kinds"] == {}


def test_strings_are_found_in_nested_payloads_and_keys() -> None:
    result = audit_stored_tokens.audit(
        [_line("report", {"sections": [{"knowledge_refs": ["{0}"]}], "Schluessel {name!r}": 1})]
    )

    report = result["kinds"]["report"]
    assert report["strings_with_hit"] == 2
    assert report["hit_strings_by_field"] == {"knowledge_refs": 1, "other": 1}
    assert report["by_bucket"] == {"v1": {"documents": 1, "with_hit": 1}}


@pytest.mark.parametrize(
    ("token", "category"),
    [
        ("<oversize>", "oversize"),
        ("[system]", "scaffolding_marker"),
        ("[ knowledge", "scaffolding_marker"),
        ("[a:", "cut_off_label"),
        ("{{", "placeholder"),
        ("{metric", "placeholder"),
        ("[a:life_path", "short_label"),
        ("{name!r}", "brace_field"),
        ("{", "single_brace"),
        ("<partner_a>", "angle_placeholder"),
        ("%(x)s", "printf_placeholder"),
    ],
)
def test_token_categories(token, category) -> None:
    assert audit_stored_tokens.classify_token(token) == category
