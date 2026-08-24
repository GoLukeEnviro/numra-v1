"""Versioned report prompts for numra-report-v3.

Markdown files under ``prompts/v3/`` are the reviewable source of truth. This module
loads them at import time so the pipeline never inlines a second copy of the text.
"""

from __future__ import annotations

from pathlib import Path

__all__ = [
    "OUTLINE_SYSTEM",
    "OUTLINE_USER_TEMPLATE",
    "PROMPT_VERSION",
    "SECTION_USER_TEMPLATE",
    "SYSTEM_INSTRUCTIONS",
    "render_outline_user",
    "render_section_user",
]

PROMPT_VERSION = "numra-report-v3"

_DIR = Path(__file__).parent / "v3"


def _read(name: str) -> str:
    return (_DIR / name).read_text(encoding="utf-8").strip()


SYSTEM_INSTRUCTIONS = _read("system.md")
SECTION_USER_TEMPLATE = _read("section_user.md")
OUTLINE_SYSTEM = _read("outline_system.md")
OUTLINE_USER_TEMPLATE = _read("outline_user.md")

_LANGUAGE_NAMES = {"de": "Deutsch", "en": "English"}


def render_section_user(
    *,
    language: str,
    section_title: str,
    section_id: str,
    min_words: int,
    max_words: int,
    planned_focus: str,
    required_placeholders: str,
    valid_metric_ids: str,
    valid_special_ids: str,
    profile_facts: str,
    knowledge_text: str,
    prior_summary: str,
    repair_block: str = "",
) -> str:
    return SECTION_USER_TEMPLATE.format(
        language_name=_LANGUAGE_NAMES.get(language, language),
        section_title=section_title,
        section_id=section_id,
        min_words=min_words,
        max_words=max_words,
        planned_focus=planned_focus or "Den Abschnitt aus den gelieferten Themen zuspitzen.",
        required_placeholders=required_placeholders or "(keine Pflicht-Platzhalter)",
        valid_metric_ids=valid_metric_ids,
        valid_special_ids=valid_special_ids,
        profile_facts=profile_facts or "(keine zusätzlichen Fakten)",
        knowledge_text=knowledge_text or "(kein Knowledge-Text)",
        prior_summary=prior_summary or "Noch nichts gesagt.",
        repair_block=repair_block.strip(),
    )


def render_outline_user(*, section_list: str, theme_bullets: str) -> str:
    return OUTLINE_USER_TEMPLATE.format(
        section_list=section_list,
        theme_bullets=theme_bullets or "(keine Themenliste)",
    )
