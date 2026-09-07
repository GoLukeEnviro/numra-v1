"""NUMRA V2 relationship/shadow-dynamics interpretation package.

Deterministic Canonical-Profile-pair + Relationship-Frame-Knowledge assembly
(`context.py`) feeding an LLM renderer (`pipeline.py`), with provenance-coverage and
forbidden-language validation (`linter.py`). No calculation logic — depends on
`numra_numerology` (canon) and `numra_interpretation` (LLM protocol + validator
reuse), never the other way around.
"""

from __future__ import annotations
