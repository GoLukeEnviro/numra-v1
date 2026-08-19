from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"

FORBIDDEN_TOKENS = [
    "Lukas",
    "LUKAS",
    "Springer",
    "SPRINGER",
    "1986-07-18",
    "18.07.1986",
    "18071986",
    "Meerbusch",
]


def test_production_source_has_no_golden_fixture_leakage() -> None:
    """canon-spec.md §37 (Anti-Cheating). Production code must never import the golden
    fixture, special-case the golden person, or hardcode a golden result as a lookup
    shortcut."""
    offenders: list[str] = []
    for path in SRC_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_TOKENS:
            if token in text:
                offenders.append(f"{path}: contains forbidden token {token!r}")
    assert not offenders, "\n".join(offenders)


def test_production_source_does_not_import_fixtures() -> None:
    offenders: list[str] = []
    for path in SRC_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "fixtures" in text or "fixtures.canonical" in text:
            offenders.append(str(path))
    assert not offenders, offenders
